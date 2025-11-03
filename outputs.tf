output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.app.dns_name
}

output "alb_url" {
  description = "Full URL to access the application"
  value       = "http://${aws_lb.app.dns_name}"
}

output "redis_endpoint" {
  description = "Primary endpoint address for Redis"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = true
}

output "redis_configuration_endpoint" {
  description = "Configuration endpoint address for Redis"
  value       = aws_elasticache_replication_group.redis.configuration_endpoint_address
  sensitive   = true
}

output "redis_secret_arn" {
  description = "ARN of the Redis authentication secret"
  value       = aws_secretsmanager_secret.redis_auth.arn
  sensitive   = true
}

output "cloudwatch_dashboard_redis" {
  description = "CloudWatch Dashboard URL for Redis metrics"
  value       = "https://${data.aws_region.current.region}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.region}#dashboards:name=${aws_cloudwatch_dashboard.redis.dashboard_name}"
}

output "cloudwatch_dashboard_app" {
  description = "CloudWatch Dashboard URL for application metrics"
  value       = "https://${data.aws_region.current.region}.console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.region}#dashboards:name=${aws_cloudwatch_dashboard.app.dashboard_name}"
}

output "app_code_bucket" {
  description = "S3 bucket name for application code"
  value       = aws_s3_bucket.app_code.id
}

output "asg_name" {
  description = "Name of the Auto Scaling Group"
  value       = aws_autoscaling_group.app.name
}
