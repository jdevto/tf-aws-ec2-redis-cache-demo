"""
Cart service for managing shopping cart operations with Redis.
"""
import json
import hashlib
from typing import Dict, Optional
from decimal import Decimal

from app.redis_client import get_redis_client
from app.config import Config
from app.models import CartItem, CartResponse
from app.exceptions import (
    CartNotFoundError,
    ValidationError,
    LimitExceededError,
    ProductNotFoundError,
    RedisConnectionError
)
from app.atomic_scripts import AtomicScripts


class CartService:
    """Service for cart operations"""

    def __init__(self):
        self.redis = get_redis_client()
        self.scripts = AtomicScripts(self.redis)

    def _get_cart_key(self, cart_id: str) -> str:
        """Generate Redis key for cart"""
        return f"cart:{cart_id}"

    def _hash_cart_id(self, cart_id: str) -> str:
        """Hash cart ID for logging (no PII)"""
        return hashlib.sha256(cart_id.encode()).hexdigest()[:8]

    def _get_ttl(self, is_guest: bool = False) -> int:
        """Get TTL for cart based on type"""
        if is_guest:
            return Config.GUEST_CART_TTL_SECONDS
        return Config.CART_TTL_SECONDS

    def add_item(
        self,
        cart_id: str,
        product_id: str,
        quantity: int,
        price: Decimal,
        variant: Optional[str] = None,
        is_guest: bool = False
    ) -> Dict:
        """
        Add or update item in cart using atomic script.

        Returns:
            Dict with operation result
        """
        if quantity <= 0:
            raise ValidationError("Quantity must be greater than 0")

        if quantity > Config.MAX_QUANTITY_PER_ITEM:
            raise LimitExceededError(
                f"Quantity {quantity} exceeds maximum {Config.MAX_QUANTITY_PER_ITEM}"
            )

        cart_key = self._get_cart_key(cart_id)
        ttl = self._get_ttl(is_guest)

        # Execute atomic add script
        try:
            result = self.scripts.add_item(
                cart_key=cart_key,
                product_id=product_id,
                quantity=quantity,
                price_snapshot=str(price),
                variant=variant or "",
                max_items=Config.MAX_ITEMS_PER_CART,
                max_quantity=Config.MAX_QUANTITY_PER_ITEM,
                ttl=ttl
            )
        except Exception as e:
            raise RedisConnectionError(f"Failed to execute Redis script: {e}")

        # Validate result
        if result is None:
            raise ValidationError("Redis script returned None - operation may have failed")

        # Handle different return types from Redis
        # With decode_responses=True, Lua tables come back as dicts or lists depending on structure
        if isinstance(result, list):
            # Empty list - script may have failed or returned nothing
            if len(result) == 0:
                # Check if item was actually added by querying Redis directly
                # If script executed but returned empty, item should still be in cart
                existing = self.redis.hget(cart_key, product_id)
                if existing:
                    # Script worked, just return value issue - reconstruct result
                    import json
                    item_data = json.loads(existing)
                    result = {
                        "ok": True,
                        "quantity": item_data.get("quantity", quantity),
                        "is_new": False
                    }
                else:
                    raise RedisConnectionError("Redis script returned empty list and item not found - script execution may have failed")
            # Single element list with dict - unwrap it
            elif len(result) == 1 and isinstance(result[0], dict):
                result = result[0]
            else:
                raise ValidationError(f"Redis script returned unexpected list format: {result}")

        if not isinstance(result, dict):
            raise ValidationError(f"Redis script returned unexpected type: {type(result)}, value: {result}")

        # Handle script errors first
        if result.get("err"):
            error = result["err"]
            if error == "MAX_QUANTITY_EXCEEDED":
                raise LimitExceededError(
                    f"Quantity exceeds maximum {result.get('max', Config.MAX_QUANTITY_PER_ITEM)}"
                )
            elif error == "MAX_ITEMS_EXCEEDED":
                raise LimitExceededError(
                    f"Cart exceeds maximum items {result.get('max', Config.MAX_ITEMS_PER_CART)}"
                )
            else:
                # Unknown error from script
                raise ValidationError(f"Redis script error: {error}")

        # Validate success response
        if not result.get("ok"):
            raise ValidationError(f"Redis script did not return success: {result}")

        # Ensure quantity is present in result
        if "quantity" not in result:
            result["quantity"] = quantity

        return result

    def update_quantity(
        self,
        cart_id: str,
        product_id: str,
        quantity: int,
        is_guest: bool = False
    ) -> Dict:
        """
        Update item quantity in cart using atomic script.

        Returns:
            Dict with operation result
        """
        if quantity < 0:
            raise ValidationError("Quantity cannot be negative")

        if quantity > Config.MAX_QUANTITY_PER_ITEM:
            raise LimitExceededError(
                f"Quantity {quantity} exceeds maximum {Config.MAX_QUANTITY_PER_ITEM}"
            )

        cart_key = self._get_cart_key(cart_id)
        ttl = self._get_ttl(is_guest)

        # Execute atomic update script
        result = self.scripts.update_quantity(
            cart_key=cart_key,
            product_id=product_id,
            quantity=quantity,
            max_quantity=Config.MAX_QUANTITY_PER_ITEM,
            ttl=ttl
        )

        # Handle script errors
        if isinstance(result, dict) and result.get("err"):
            error = result["err"]
            if error == "PRODUCT_NOT_FOUND":
                raise ProductNotFoundError(product_id)
            elif error == "MAX_QUANTITY_EXCEEDED":
                raise LimitExceededError(
                    f"Quantity exceeds maximum {result.get('max', Config.MAX_QUANTITY_PER_ITEM)}"
                )

        return result

    def remove_item(self, cart_id: str, product_id: str, is_guest: bool = False) -> bool:
        """Remove item from cart"""
        cart_key = self._get_cart_key(cart_id)
        ttl = self._get_ttl(is_guest)

        # Delete field from hash
        deleted = self.redis.hdel(cart_key, product_id)

        if deleted > 0:
            # Refresh TTL if cart still has items
            item_count = self.redis.hlen(cart_key)
            if item_count > 0:
                self.redis.expire(cart_key, ttl)
            else:
                # Delete cart if empty
                self.redis.delete(cart_key)
            return True

        return False

    def get_cart(self, cart_id: str) -> CartResponse:
        """Get cart contents"""
        cart_key = self._get_cart_key(cart_id)

        # Check if cart exists
        if not self.redis.exists(cart_key):
            raise CartNotFoundError(cart_id)

        # Get all items from hash
        items_data = self.redis.hgetall(cart_key)

        if not items_data:
            # Empty cart
            return CartResponse(
                cart_id=cart_id,
                items={},
                total_items=0,
                total_price=Decimal("0")
            )

        # Parse items
        items: Dict[str, CartItem] = {}
        total_price = Decimal("0")
        total_items = 0

        for product_id, item_json in items_data.items():
            try:
                item_data = json.loads(item_json)
                item = CartItem(
                    product_id=product_id,
                    quantity=item_data["quantity"],
                    price_snapshot=Decimal(str(item_data["price_snapshot"])),
                    variant=item_data.get("variant")
                )
                items[product_id] = item
                total_price += item.price_snapshot * item.quantity
                total_items += item.quantity
            except (json.JSONDecodeError, KeyError) as e:
                # Skip invalid items
                print(f"Warning: Failed to parse cart item {product_id}: {e}")
                continue

        return CartResponse(
            cart_id=cart_id,
            items=items,
            total_items=total_items,
            total_price=total_price
        )

    def clear_cart(self, cart_id: str) -> bool:
        """Clear all items from cart"""
        cart_key = self._get_cart_key(cart_id)
        deleted = self.redis.delete(cart_key)
        return deleted > 0

    def merge_carts(
        self,
        source_cart_id: str,
        target_cart_id: str,
        conflict_resolution: str = "sum",
        is_guest: bool = False
    ) -> Dict:
        """
        Merge source cart into target cart using atomic script.

        Args:
            source_cart_id: Cart to merge from (usually guest)
            target_cart_id: Cart to merge into (usually user)
            conflict_resolution: 'sum' or 'last-write-wins'

        Returns:
            Dict with merge result
        """
        if conflict_resolution not in ["sum", "last-write-wins"]:
            raise ValidationError("conflict_resolution must be 'sum' or 'last-write-wins'")

        source_key = self._get_cart_key(source_cart_id)
        target_key = self._get_cart_key(target_cart_id)
        ttl = self._get_ttl(is_guest=False)  # Target is always user cart

        # Check if source cart exists
        if not self.redis.exists(source_key):
            return {
                "ok": True,
                "merged": 0,
                "conflicts": 0,
                "message": "Source cart is empty"
            }

        # Execute atomic merge script
        result = self.scripts.merge_cart(
            source_key=source_key,
            target_key=target_key,
            conflict_resolution=conflict_resolution,
            ttl=ttl
        )

        return result
