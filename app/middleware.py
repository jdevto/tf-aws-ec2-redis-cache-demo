"""
Middleware for FastAPI: metrics, logging, error handling.
"""
import time
import hashlib
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def hash_identifier(identifier: str) -> str:
    """Hash identifier for logging (no PII)"""
    return hashlib.sha256(identifier.encode()).hexdigest()[:8]


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting metrics"""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()

        # Extract cart/user identifiers for logging (hashed)
        cart_id = request.query_params.get("cart_id") or request.headers.get("X-Cart-ID")
        user_id = request.headers.get("X-User-ID")

        hashed_cart_id = hash_identifier(cart_id) if cart_id else None
        hashed_user_id = hash_identifier(user_id) if user_id else None

        # Log request (no PII)
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "hashed_cart_id": hashed_cart_id,
                "hashed_user_id": hashed_user_id,
                "remote_addr": request.client.host if request.client else None
            }
        )

        try:
            response = await call_next(request)

            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000

            # Log response
            logger.info(
                f"Response: {request.method} {request.url.path} {response.status_code}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": round(latency_ms, 2),
                    "hashed_cart_id": hashed_cart_id
                }
            )

            # Add latency header
            response.headers["X-Response-Time-Ms"] = f"{latency_ms:.2f}"

            # Publish custom metrics to CloudWatch (simulated)
            # In production, use boto3 to publish metrics
            if hasattr(request.state, "metric_name"):
                metric_name = request.state.metric_name
                logger.info(
                    f"Metric: {metric_name}",
                    extra={
                        "metric_name": metric_name,
                        "value": getattr(request.state, "metric_value", 1),
                        "latency_ms": round(latency_ms, 2)
                    }
                )

            return response

        except Exception as e:
            # Log errors
            logger.error(
                f"Error: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "hashed_cart_id": hashed_cart_id
                },
                exc_info=True
            )

            # Re-raise the exception to let FastAPI handle it properly
            # This allows route-level exception handlers to work
            raise
