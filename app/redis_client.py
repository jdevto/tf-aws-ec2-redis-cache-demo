"""
Redis client wrapper with connection pooling, retry logic, and error handling.
"""
import redis
import time
import random
import json
from typing import Optional, Any, Callable
from redis.exceptions import (
    ConnectionError,
    TimeoutError,
    RedisError,
    AuthenticationError
)

from app.config import Config
from app.exceptions import RedisConnectionError


class RedisClient:
    """Redis client with connection pooling and retry logic"""

    def __init__(self):
        self.pool: Optional[redis.ConnectionPool] = None
        self.client: Optional[redis.Redis] = None
        self._connect()

    def _connect(self):
        """Initialize Redis connection pool"""
        try:
            # Use rediss:// protocol for SSL/TLS connection
            # ElastiCache with encryption-in-transit requires SSL
            redis_url = f"rediss://:{Config.REDIS_AUTH_TOKEN}@{Config.REDIS_HOST}:{Config.REDIS_PORT}/{Config.REDIS_DB}"

            self.pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=Config.REDIS_MAX_CONNECTIONS,
                socket_connect_timeout=Config.REDIS_SOCKET_CONNECT_TIMEOUT,
                socket_timeout=Config.REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=Config.REDIS_RETRY_ON_TIMEOUT,
                decode_responses=True,
                ssl_cert_reqs=None  # Don't verify certificates (ElastiCache uses self-signed certs)
            )

            self.client = redis.Redis(connection_pool=self.pool)

            # Test connection
            self.client.ping()

        except (ConnectionError, AuthenticationError) as e:
            raise RedisConnectionError(f"Failed to connect to Redis: {e}")

    def _retry_with_backoff(
        self,
        func: Callable,
        max_retries: int = 3,
        initial_backoff: float = 0.1,
        max_backoff: float = 2.0
    ) -> Any:
        """
        Execute function with exponential backoff retry.

        Args:
            func: Function to execute
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds

        Returns:
            Result of function execution

        Raises:
            RedisConnectionError: If all retries fail
        """
        backoff = initial_backoff

        for attempt in range(max_retries):
            try:
                return func()
            except (ConnectionError, TimeoutError) as e:
                if attempt == max_retries - 1:
                    # Last attempt failed, raise error
                    raise RedisConnectionError(f"Redis operation failed after {max_retries} retries: {e}")

                # Exponential backoff with jitter
                jitter = random.uniform(0, backoff * 0.1)
                time.sleep(backoff + jitter)
                backoff = min(backoff * 2, max_backoff)

                # Try to reconnect
                try:
                    self._connect()
                except Exception:
                    pass  # Continue with retry

            except RedisError as e:
                # Non-retryable errors
                raise RedisConnectionError(f"Redis error: {e}")

    def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        def _get():
            return self.client.get(key)
        return self._retry_with_backoff(_get)

    def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set value in Redis with optional TTL"""
        def _set():
            return self.client.set(key, value, ex=ex)
        return self._retry_with_backoff(_set)

    def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        def _delete():
            return self.client.delete(*keys)
        return self._retry_with_backoff(_delete)

    def exists(self, *keys: str) -> int:
        """Check if keys exist"""
        def _exists():
            return self.client.exists(*keys)
        return self._retry_with_backoff(_exists)

    def expire(self, key: str, time: int) -> bool:
        """Set TTL on a key"""
        def _expire():
            return self.client.expire(key, time)
        return self._retry_with_backoff(_expire)

    def hget(self, key: str, field: str) -> Optional[str]:
        """Get field from hash"""
        def _hget():
            return self.client.hget(key, field)
        return self._retry_with_backoff(_hget)

    def hset(self, key: str, field: str, value: Any) -> int:
        """Set field in hash"""
        def _hset():
            return self.client.hset(key, field, value)
        return self._retry_with_backoff(_hset)

    def hdel(self, key: str, *fields: str) -> int:
        """Delete fields from hash"""
        def _hdel():
            return self.client.hdel(key, *fields)
        return self._retry_with_backoff(_hdel)

    def hgetall(self, key: str) -> dict:
        """Get all fields from hash"""
        def _hgetall():
            return self.client.hgetall(key)
        return self._retry_with_backoff(_hgetall)

    def hlen(self, key: str) -> int:
        """Get number of fields in hash"""
        def _hlen():
            return self.client.hlen(key)
        return self._retry_with_backoff(_hlen)

    def hincrby(self, key: str, field: str, amount: int = 1) -> int:
        """Increment field in hash"""
        def _hincrby():
            return self.client.hincrby(key, field, amount)
        return self._retry_with_backoff(_hincrby)

    def eval(self, script: str, num_keys: int, *keys_and_args) -> Any:
        """Execute Lua script"""
        def _eval():
            return self.client.eval(script, num_keys, *keys_and_args)
        return self._retry_with_backoff(_eval)

    def register_script(self, script: str):
        """Register a Lua script for repeated execution"""
        return self.client.register_script(script)

    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return self.client.ping()
        except Exception:
            return False

    def close(self):
        """Close connection pool"""
        if self.pool:
            self.pool.disconnect()


# Global Redis client instance
_redis_client: Optional[RedisClient] = None

def get_redis_client() -> RedisClient:
    """Get or create Redis client instance (singleton)"""
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
