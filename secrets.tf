# =============================================================================
# SECRETS MANAGER
# =============================================================================

# Redis Authentication Token in Secrets Manager
resource "aws_secretsmanager_secret" "redis_auth" {
  name        = "${var.project_name}-redis-auth"
  description = "Redis authentication token for ElastiCache"

  recovery_window_in_days = 0 # Allow immediate deletion

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-auth"
  })
}

# Store the Redis auth token in Secrets Manager
resource "aws_secretsmanager_secret_version" "redis_auth" {
  secret_id = aws_secretsmanager_secret.redis_auth.id
  secret_string = jsonencode({
    auth_token = random_password.redis_auth.result
    endpoint   = aws_elasticache_replication_group.redis.primary_endpoint_address
  })

  depends_on = [aws_elasticache_replication_group.redis]
}
