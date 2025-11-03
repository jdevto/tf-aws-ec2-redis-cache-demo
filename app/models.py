"""
Pydantic models for cart operations, requests, and responses.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, List
from decimal import Decimal

class CartItem(BaseModel):
    """Cart item model"""
    product_id: str = Field(..., description="Product identifier")
    quantity: int = Field(..., ge=0, description="Item quantity")
    price_snapshot: Decimal = Field(..., description="Price at time of add")
    variant: Optional[str] = Field(None, description="Product variant/option")

    @field_validator('quantity')
    @classmethod
    def validate_quantity(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Quantity cannot be negative")
        return v

class CartItemRequest(BaseModel):
    """Request model for adding/updating cart items"""
    product_id: str = Field(..., description="Product identifier")
    quantity: int = Field(..., ge=0, description="Item quantity")
    price: Decimal = Field(..., description="Product price")
    variant: Optional[str] = Field(None, description="Product variant/option")

class CartResponse(BaseModel):
    """Response model for cart retrieval"""
    cart_id: str = Field(..., description="Cart identifier")
    items: Dict[str, CartItem] = Field(default_factory=dict, description="Cart items by product_id")
    total_items: int = Field(0, description="Total number of items")
    total_price: Decimal = Field(Decimal("0"), description="Total cart price")

class MergeCartRequest(BaseModel):
    """Request model for merging carts"""
    source_cart_id: str = Field(..., description="Cart ID to merge from (usually guest cart)")
    target_cart_id: str = Field(..., description="Cart ID to merge into (usually user cart)")
    conflict_resolution: str = Field("sum", description="Conflict resolution: 'sum' or 'last-write-wins'")

class CheckoutRequest(BaseModel):
    """Request model for checkout"""
    cart_id: str = Field(..., description="Cart identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    validate_pricing: bool = Field(True, description="Whether to validate pricing at checkout")

class CheckoutResponse(BaseModel):
    """Response model for checkout"""
    order_id: str = Field(..., description="Generated order identifier")
    cart_id: str = Field(..., description="Cart identifier that was checked out")
    total: Decimal = Field(..., description="Order total")
    items: List[CartItem] = Field(..., description="Ordered items")
    message: str = Field(..., description="Checkout status message")
