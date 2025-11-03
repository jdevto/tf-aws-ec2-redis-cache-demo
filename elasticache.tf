# =============================================================================
# ELASTICACHE REDIS
# =============================================================================

# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "redis" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-subnet-group"
  })
}

# ElastiCache Parameter Group
resource "aws_elasticache_parameter_group" "redis" {
  name   = "${var.project_name}-redis-params"
  family = "redis7"

  parameter {
    name  = "maxmemory-policy"
    value = "volatile-ttl"
  }

  parameter {
    name  = "timeout"
    value = "300"
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-params"
  })
}

# ElastiCache Replication Group (Multi-AZ)
resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = substr("${var.project_name}-redis", 0, 40)
  description          = "Redis cluster for shopping cart cache"

  engine             = "redis"
  engine_version     = "7.0"
  node_type          = var.redis_node_type
  num_cache_clusters = var.redis_num_cache_nodes

  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.redis.name
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  # Multi-AZ configuration
  multi_az_enabled           = true
  automatic_failover_enabled = true

  # No persistence for ephemeral cart data
  snapshot_retention_limit  = 0
  final_snapshot_identifier = null

  # Authentication (requires encryption-in-transit)
  auth_token                 = random_password.redis_auth.result
  transit_encryption_enabled = true # Required when using AUTH token

  # Logging
  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_slow.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "slow-log"
  }

  log_delivery_configuration {
    destination      = aws_cloudwatch_log_group.redis_engine.name
    destination_type = "cloudwatch-logs"
    log_format       = "text"
    log_type         = "engine-log"
  }

  # Force destroy allowed
  apply_immediately = true

  # Preferred AZ for primary node (same as app)
  preferred_cache_cluster_azs = var.availability_zones

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis"
  })

  depends_on = [
    aws_cloudwatch_log_group.redis_slow,
    aws_cloudwatch_log_group.redis_engine
  ]
}
