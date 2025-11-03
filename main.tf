# Data source to get current AWS region
data "aws_region" "current" {}

# Random ID for S3 bucket name uniqueness
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# Generate random password for Redis authentication (alphanumeric only - no special chars allowed)
resource "random_password" "redis_auth" {
  length  = 32
  special = false
  upper   = true
  lower   = true
  numeric = true
}

# Get current user's public IP
data "http" "my_public_ip" {
  url = "https://checkip.amazonaws.com/"
}
