"""
Configuration management for the shopping cart application.
Loads settings from environment variables and AWS Secrets Manager.
"""
import os
import json
import boto3
from typing import Optional

class Config:
    """Application configuration"""

    # Application settings
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "terraform-aws-demo")
    REGION: str = os.getenv("REGION", "ap-southeast-2")

    # Redis settings
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_AUTH_TOKEN: Optional[str] = os.getenv("REDIS_AUTH_TOKEN")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))

    # Cart settings
    CART_TTL_SECONDS: int = int(os.getenv("CART_TTL_SECONDS", str(7 * 24 * 60 * 60)))  # 7 days default
    GUEST_CART_TTL_SECONDS: int = int(os.getenv("GUEST_CART_TTL_SECONDS", str(1 * 24 * 60 * 60)))  # 1 day for guests
    MAX_ITEMS_PER_CART: int = int(os.getenv("MAX_ITEMS_PER_CART", "200"))
    MAX_QUANTITY_PER_ITEM: int = int(os.getenv("MAX_QUANTITY_PER_ITEM", "99"))

    # Redis connection settings
    REDIS_SOCKET_CONNECT_TIMEOUT: int = 5
    REDIS_SOCKET_TIMEOUT: int = 5
    REDIS_RETRY_ON_TIMEOUT: bool = True
    REDIS_MAX_CONNECTIONS: int = 50

    @classmethod
    def load_redis_secrets(cls) -> None:
        """Load Redis authentication token from AWS Secrets Manager"""
        if cls.REDIS_AUTH_TOKEN:
            return  # Already loaded from environment

        secret_name = os.getenv("REDIS_SECRET_NAME")
        if not secret_name:
            return  # No secret name provided, use no auth

        try:
            client = boto3.client("secretsmanager", region_name=cls.REGION)
            response = client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response["SecretString"])

            cls.REDIS_AUTH_TOKEN = secret_data.get("auth_token")
            if "endpoint" in secret_data:
                cls.REDIS_HOST = secret_data["endpoint"]
        except Exception as e:
            print(f"Warning: Could not load Redis secrets from Secrets Manager: {e}")
            # Continue without auth token (may fail on connection)

# Load secrets at module import
Config.load_redis_secrets()
