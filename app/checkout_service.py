"""
Checkout service for validating and processing cart checkout.
"""
import uuid
from typing import Dict, Optional
from decimal import Decimal

from app.cart_service import CartService
from app.models import CartResponse, CheckoutResponse, CartItem
from app.exceptions import CartNotFoundError, ValidationError


class CheckoutService:
    """Service for checkout operations"""

    def __init__(self):
        self.cart_service = CartService()

    def start_checkout(
        self,
        cart_id: str,
        user_id: Optional[str] = None,
        validate_pricing: bool = True
    ) -> CheckoutResponse:
        """
        Start checkout process:
        1. Get cart contents
        2. Validate pricing (if enabled)
        3. Validate inventory (simulated)
        4. Generate order ID
        5. Persist to database (simulated)
        6. Clear cart from Redis

        Args:
            cart_id: Cart identifier
            user_id: User identifier (optional)
            validate_pricing: Whether to validate pricing at checkout

        Returns:
            CheckoutResponse with order details
        """
        # Get cart contents
        try:
            cart = self.cart_service.get_cart(cart_id)
        except CartNotFoundError:
            raise ValidationError(f"Cart {cart_id} not found or already checked out")

        if not cart.items:
            raise ValidationError("Cannot checkout empty cart")

        # Validate pricing (simulate price validation)
        price_changes = []
        if validate_pricing:
            # In real implementation, this would fetch current prices from DB
            # and compare with price_snapshot
            for product_id, item in cart.items.items():
                # Simulate price check (always matches for demo)
                # In production: fetch_price(product_id) != item.price_snapshot
                pass

        # Validate inventory (simulated)
        inventory_issues = []
        for product_id, item in cart.items.items():
            # In real implementation, check stock levels
            # For demo, simulate stock check
            available_stock = 999  # Simulated
            if item.quantity > available_stock:
                inventory_issues.append({
                    "product_id": product_id,
                    "requested": item.quantity,
                    "available": available_stock
                })

        if inventory_issues:
            raise ValidationError(
                f"Insufficient inventory for products: {inventory_issues}"
            )

        # Generate order ID
        order_id = str(uuid.uuid4())

        # Persist to database (simulated)
        # In real implementation, this would insert into orders table
        order_data = {
            "order_id": order_id,
            "cart_id": cart_id,
            "user_id": user_id,
            "items": [
                {
                    "product_id": item.product_id,
                    "quantity": item.quantity,
                    "price": float(item.price_snapshot),
                    "variant": item.variant
                }
                for item in cart.items.values()
            ],
            "total": float(cart.total_price),
            "timestamp": "2024-01-01T00:00:00Z"  # Would use actual timestamp
        }

        # Log order creation (simulated DB write)
        print(f"[SIMULATED DB] Order created: {order_id}, Total: ${cart.total_price}")

        # Clear cart from Redis
        self.cart_service.clear_cart(cart_id)

        # Convert cart items to list for response
        items_list = list(cart.items.values())

        return CheckoutResponse(
            order_id=order_id,
            cart_id=cart_id,
            total=cart.total_price,
            items=items_list,
            message="Order placed successfully. Cart has been cleared."
        )
