"""
FastAPI application for shopping cart with Redis cache.
"""
import time
import os
from typing import Optional
from decimal import Decimal
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import Config
from app.models import (
    CartItemRequest,
    CartResponse,
    MergeCartRequest,
    CheckoutRequest,
    CheckoutResponse
)
from app.cart_service import CartService
from app.checkout_service import CheckoutService
from app.exceptions import (
    CartNotFoundError,
    ValidationError,
    LimitExceededError,
    ProductNotFoundError,
    RedisConnectionError
)
from app.middleware import MetricsMiddleware
from app.redis_client import get_redis_client

# Initialize FastAPI app
app = FastAPI(
    title="Shopping Cart API",
    description="Shopping cart service with Redis cache",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Metrics middleware
app.add_middleware(MetricsMiddleware)

# Mount static files
try:
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
except Exception:
    pass  # Static directory may not exist during development

# Initialize services
cart_service = CartService()
checkout_service = CheckoutService()

# Get instance ID from IMDS (cached)
_instance_id: Optional[str] = None

def get_instance_id() -> str:
    """Get EC2 instance ID from IMDS"""
    global _instance_id
    if _instance_id:
        return _instance_id

    try:
        import urllib.request
        import urllib.error

        # Try IMDSv2 first (token-based)
        try:
            token_url = "http://169.254.169.254/latest/api/token"
            token_req = urllib.request.Request(token_url, method="PUT")
            token_req.add_header("X-aws-ec2-metadata-token-ttl-seconds", "21600")

            with urllib.request.urlopen(token_req, timeout=2) as response:
                token = response.read().decode().strip()

            instance_url = "http://169.254.169.254/latest/meta-data/instance-id"
            instance_req = urllib.request.Request(instance_url)
            instance_req.add_header("X-aws-ec2-metadata-token", token)

            with urllib.request.urlopen(instance_req, timeout=2) as response:
                _instance_id = response.read().decode().strip()
            return _instance_id
        except (urllib.error.URLError, urllib.error.HTTPError, Exception):
            # Fallback to IMDSv1 if v2 fails
            instance_url = "http://169.254.169.254/latest/meta-data/instance-id"
            with urllib.request.urlopen(instance_url, timeout=2) as response:
                _instance_id = response.read().decode().strip()
            return _instance_id
    except Exception as e:
        # Fallback if not on EC2 or IMDS unavailable
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not fetch instance ID from IMDS: {e}")
        return os.getenv("INSTANCE_ID", "unknown")


# Health check endpoint for ALB
@app.get("/health")
async def health_check():
    """
    Health check endpoint for ALB.
    Always returns HTTP 200 if the application is running.
    Checks Redis connectivity but does not fail if Redis is unavailable.
    """
    redis_status = "healthy"
    redis_latency_ms = None

    try:
        redis_client = get_redis_client()
        ping_start = time.time()
        ping_result = redis_client.ping()
        redis_latency_ms = round((time.time() - ping_start) * 1000, 2)

        if not ping_result:
            redis_status = "unhealthy"
    except Exception as e:
        redis_status = "unhealthy"

    # Always return 200 for ALB health checks
    # ALB just needs to know the application is responding
    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",  # Always healthy from ALB perspective
            "service": "cart-api",
            "redis": {
                "status": redis_status,
                "latency_ms": redis_latency_ms
            },
            "timestamp": time.time()
        }
    )


# Metadata endpoint
@app.get("/metadata")
async def get_metadata():
    """Get instance metadata for demo display"""
    return {
        "instance_id": get_instance_id()
    }


# Root endpoint - serve frontend
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve frontend application"""
    try:
        with open("app/static/index.html", "r") as f:
            return f.read()
    except FileNotFoundError:
        return """
        <html>
            <body>
                <h1>Shopping Cart API</h1>
                <p>API is running. Frontend not found.</p>
                <p>Health check: <a href="/health">/health</a></p>
            </body>
        </html>
        """


# Cart endpoints
@app.post("/cart/items", response_model=dict)
async def add_cart_item(
    request: CartItemRequest,
    cart_id: str = Header(..., alias="X-Cart-ID", description="Cart identifier"),
    user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier")
):
    """
    Add or update item in cart.
    Uses atomic Lua script for thread-safe operations.
    """
    # Validate cart_id
    if not cart_id or not cart_id.strip():
        raise HTTPException(status_code=400, detail="Cart ID is required")

    cart_id = cart_id.strip()

    start_time = time.time()

    try:
        is_guest = user_id is None
        result = cart_service.add_item(
            cart_id=cart_id,
            product_id=request.product_id,
            quantity=request.quantity,
            price=request.price,
            variant=request.variant,
            is_guest=is_guest
        )

        latency_ms = (time.time() - start_time) * 1000

        # Extract quantity from result, ensuring it's an integer
        # The script should always return quantity, but we have a fallback
        quantity_result = result.get("quantity")
        if quantity_result is None:
            # Fallback: use requested quantity if script didn't return it
            quantity_result = request.quantity
        else:
            # Convert to int (handles both int and string from Lua)
            try:
                quantity_result = int(quantity_result)
            except (ValueError, TypeError):
                quantity_result = request.quantity

        return {
            "success": True,
            "message": "Item added to cart",
            "product_id": request.product_id,
            "quantity": quantity_result,
            "latency_ms": round(latency_ms, 2),
            "cached": True
        }

    except (ValidationError, LimitExceededError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error adding item to cart: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add item: {str(e)}")


@app.get("/cart", response_model=CartResponse)
async def get_cart(
    cart_id: str = Header(..., alias="X-Cart-ID", description="Cart identifier")
):
    """
    Get cart contents.
    Retrieves all items from Redis hash.
    Returns empty cart if cart doesn't exist yet.
    """
    # Validate cart_id
    if not cart_id or not cart_id.strip():
        raise HTTPException(status_code=400, detail="Cart ID is required")

    cart_id = cart_id.strip()
    start_time = time.time()

    try:
        cart = cart_service.get_cart(cart_id)
        latency_ms = (time.time() - start_time) * 1000

        # Add latency to response
        return {
            **cart.model_dump(),
            "latency_ms": round(latency_ms, 2),
            "cached": True
        }

    except CartNotFoundError:
        # Return empty cart instead of 404 for better UX
        latency_ms = (time.time() - start_time) * 1000
        return {
            "cart_id": cart_id,
            "items": {},
            "total_items": 0,
            "total_price": Decimal("0"),
            "latency_ms": round(latency_ms, 2),
            "cached": False
        }
    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.delete("/cart/items/{product_id}", response_model=dict)
async def remove_cart_item(
    product_id: str,
    cart_id: str = Header(..., alias="X-Cart-ID", description="Cart identifier"),
    user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier")
):
    """Remove item from cart"""
    start_time = time.time()

    try:
        is_guest = user_id is None
        removed = cart_service.remove_item(cart_id, product_id, is_guest)

        if not removed:
            raise HTTPException(status_code=404, detail="Product not found in cart")

        latency_ms = (time.time() - start_time) * 1000

        return {
            "success": True,
            "message": "Item removed from cart",
            "product_id": product_id,
            "latency_ms": round(latency_ms, 2),
            "cached": True
        }

    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.post("/cart/merge", response_model=dict)
async def merge_carts(
    request: MergeCartRequest
):
    """
    Merge two carts atomically.
    Typically used to merge guest cart into user cart on login.
    """
    start_time = time.time()

    try:
        result = cart_service.merge_carts(
            source_cart_id=request.source_cart_id,
            target_cart_id=request.target_cart_id,
            conflict_resolution=request.conflict_resolution
        )

        latency_ms = (time.time() - start_time) * 1000

        return {
            "success": True,
            "message": "Carts merged successfully",
            "merged_items": result.get("merged", 0),
            "conflicts": result.get("conflicts", 0),
            "resolution": result.get("resolution", request.conflict_resolution),
            "latency_ms": round(latency_ms, 2),
            "cached": True
        }

    except (ValidationError, CartNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


@app.post("/checkout/start", response_model=CheckoutResponse)
async def start_checkout(
    request: CheckoutRequest,
    user_id: Optional[str] = Header(None, alias="X-User-ID", description="User identifier")
):
    """
    Start checkout process.
    Validates cart, creates order, and clears cart from Redis.
    """
    start_time = time.time()

    try:
        checkout_result = checkout_service.start_checkout(
            cart_id=request.cart_id,
            user_id=user_id or request.user_id,
            validate_pricing=request.validate_pricing
        )

        latency_ms = (time.time() - start_time) * 1000

        # Add latency to response
        result_dict = checkout_result.model_dump()
        result_dict["latency_ms"] = round(latency_ms, 2)

        return result_dict

    except (ValidationError, CartNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RedisConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")


# Error handlers
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "message": str(exc)}
    )


@app.exception_handler(CartNotFoundError)
async def cart_not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={"error": "Cart not found", "message": str(exc)}
    )


@app.exception_handler(RedisConnectionError)
async def redis_error_handler(request, exc):
    return JSONResponse(
        status_code=503,
        content={"error": "Service unavailable", "message": "Redis connection failed"}
    )


# Generic exception handler for unhandled errors
@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=Config.APP_PORT)
