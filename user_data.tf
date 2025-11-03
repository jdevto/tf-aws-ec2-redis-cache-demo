# =============================================================================
# USER DATA SCRIPT FOR EC2 INSTANCES
# =============================================================================

data "template_file" "user_data" {
  template = file("${path.module}/user_data.sh")

  vars = {
    app_port          = var.app_port
    redis_endpoint    = aws_elasticache_replication_group.redis.primary_endpoint_address
    redis_secret_name = aws_secretsmanager_secret.redis_auth.name
    region            = data.aws_region.current.region
    project_name      = var.project_name
    app_code_bucket   = aws_s3_bucket.app_code.id
  }

  depends_on = [
    aws_elasticache_replication_group.redis,
    aws_secretsmanager_secret_version.redis_auth,
    aws_s3_object.app_files,
    aws_s3_object.app_static
  ]
}
