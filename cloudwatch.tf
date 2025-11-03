# =============================================================================
# CLOUDWATCH DASHBOARDS AND ALARMS
# =============================================================================

# CloudWatch Dashboard for Redis Metrics
resource "aws_cloudwatch_dashboard" "redis" {
  dashboard_name = "${var.project_name}-redis-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "CPUUtilization", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            ["AWS/ElastiCache", "NetworkBytesIn", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            ["AWS/ElastiCache", "NetworkBytesOut", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.region
          title  = "Redis - CPU and Network"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "BytesReadFromCache", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            ["AWS/ElastiCache", "BytesWrittenToCache", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.region
          title  = "Redis - Data Transfer"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "DatabaseMemoryUsagePercentage", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            [".", "FreeableMemory", ".", "."],
            [".", "Evictions", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.region
          title  = "Redis - Memory Usage and Evictions"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 18
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "CurrConnections", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            [".", "NewConnections", ".", "."],
            [".", "ReplicationLag", ".", "."]
          ]
          period = 300
          stat   = "Average"
          region = data.aws_region.current.region
          title  = "Redis - Connections and Replication Lag"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 24
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/ElastiCache", "CacheHits", "ReplicationGroupId", aws_elasticache_replication_group.redis.replication_group_id],
            [".", "CacheMisses", ".", "."],
            [".", "KeyspaceHits", ".", "."],
            [".", "KeyspaceMisses", ".", "."]
          ]
          period = 300
          stat   = "Sum"
          region = data.aws_region.current.region
          title  = "Redis - Cache Hit/Miss Rates"
        }
      }
    ]
  })
}

# CloudWatch Dashboard for Application Metrics
resource "aws_cloudwatch_dashboard" "app" {
  dashboard_name = "${var.project_name}-app-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["${var.project_name}/cart", "cart_operations_total", { stat = "Sum" }],
            [".", "cart_add_operations", { stat = "Sum" }],
            [".", "cart_update_operations", { stat = "Sum" }],
            [".", "cart_get_operations", { stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = data.aws_region.current.region
          title  = "Cart Operations Count"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["${var.project_name}/cart", "cart_operation_latency", { stat = "Average" }],
            [".", "redis_operation_latency", { stat = "Average" }]
          ]
          period = 60
          stat   = "Average"
          region = data.aws_region.current.region
          title  = "Operation Latency (ms)"
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["${var.project_name}/cart", "cart_errors_total", { stat = "Sum" }],
            [".", "redis_connection_errors", { stat = "Sum" }],
            [".", "merge_conflicts", { stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = data.aws_region.current.region
          title  = "Error Counts"
        }
      }
    ]
  })
}

# CloudWatch Alarms for Redis
resource "aws_cloudwatch_metric_alarm" "redis_high_memory" {
  alarm_name          = "${var.project_name}-redis-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseMemoryUsagePercentage"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "This metric monitors Redis memory usage"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis.replication_group_id
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-high-memory-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_high_cpu" {
  alarm_name          = "${var.project_name}-redis-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "This metric monitors Redis CPU utilization"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis.replication_group_id
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-high-cpu-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "redis_failover" {
  alarm_name          = "${var.project_name}-redis-failover"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ReplicationLag"
  namespace           = "AWS/ElastiCache"
  period              = 60
  statistic           = "Maximum"
  threshold           = 10
  alarm_description   = "This metric monitors Redis replication lag"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ReplicationGroupId = aws_elasticache_replication_group.redis.replication_group_id
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-failover-alarm"
  })
}

# VPC Flow Logs
resource "aws_flow_log" "vpc" {
  iam_role_arn    = aws_iam_role.vpc_flow_log.arn
  log_destination = aws_cloudwatch_log_group.vpc_flow_logs.arn
  traffic_type    = "ALL"
  vpc_id          = aws_vpc.this.id

  tags = merge(local.tags, {
    Name = "${var.project_name}-vpc-flow-log"
  })
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/${var.project_name}/flow-logs"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-vpc-flow-logs"
  })
}

# CloudWatch Log Groups for Redis
resource "aws_cloudwatch_log_group" "redis_slow" {
  name              = "/aws/elasticache/${var.project_name}/slow-log"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-slow-log"
  })
}

resource "aws_cloudwatch_log_group" "redis_engine" {
  name              = "/aws/elasticache/${var.project_name}/engine-log"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-engine-log"
  })
}

# CloudWatch Log Group for application logs
resource "aws_cloudwatch_log_group" "app" {
  name              = "/aws/ec2/${var.project_name}/app"
  retention_in_days = 1

  lifecycle {
    prevent_destroy = false
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-app-log"
  })
}
