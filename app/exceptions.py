"""
Custom exceptions for the shopping cart application.
"""
from typing import Optional

class CartException(Exception):
    """Base exception for cart operations"""
    pass

class CartNotFoundError(CartException):
    """Raised when a cart does not exist"""
    def __init__(self, cart_id: str):
        self.cart_id = cart_id
        super().__init__(f"Cart not found: {cart_id}")

class ValidationError(CartException):
    """Raised when validation fails"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class LimitExceededError(CartException):
    """Raised when cart limits are exceeded"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)

class RedisConnectionError(CartException):
    """Raised when Redis connection fails"""
    pass

class ProductNotFoundError(CartException):
    """Raised when a product is not found in cart"""
    def __init__(self, product_id: str):
        self.product_id = product_id
        super().__init__(f"Product not found in cart: {product_id}")
