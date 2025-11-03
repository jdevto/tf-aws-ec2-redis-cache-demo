# S3 Bucket for Application Code
resource "aws_s3_bucket" "app_code" {
  bucket = "${var.project_name}-app-code-${random_id.bucket_suffix.hex}"

  force_destroy = true

  tags = merge(local.tags, {
    Name = "${var.project_name}-app-code"
  })
}

resource "aws_s3_bucket_ownership_controls" "app_code" {
  bucket = aws_s3_bucket.app_code.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_versioning" "app_code" {
  bucket = aws_s3_bucket.app_code.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "app_code" {
  bucket = aws_s3_bucket.app_code.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "app_code" {
  bucket = aws_s3_bucket.app_code.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Upload application files to S3
resource "aws_s3_object" "app_files" {
  for_each = {
    "__init__.py"         = file("${path.module}/app/__init__.py")
    "config.py"           = file("${path.module}/app/config.py")
    "exceptions.py"       = file("${path.module}/app/exceptions.py")
    "models.py"           = file("${path.module}/app/models.py")
    "redis_client.py"     = file("${path.module}/app/redis_client.py")
    "atomic_scripts.py"   = file("${path.module}/app/atomic_scripts.py")
    "cart_service.py"     = file("${path.module}/app/cart_service.py")
    "checkout_service.py" = file("${path.module}/app/checkout_service.py")
    "middleware.py"       = file("${path.module}/app/middleware.py")
    "main.py"             = file("${path.module}/app/main.py")
    "requirements.txt"    = file("${path.module}/app/requirements.txt")
  }

  bucket  = aws_s3_bucket.app_code.id
  key     = "app/${each.key}"
  content = each.value

  content_type = each.key == "requirements.txt" ? "text/plain" : "text/x-python"

  tags = merge(local.tags, {
    Name = "${var.project_name}-app-${each.key}"
  })
}

resource "aws_s3_object" "app_static" {
  bucket       = aws_s3_bucket.app_code.id
  key          = "app/static/index.html"
  content      = file("${path.module}/app/static/index.html")
  content_type = "text/html"

  tags = merge(local.tags, {
    Name = "${var.project_name}-app-index"
  })
}

# S3 Bucket for ALB Access Logs
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-alb-logs-${random_id.bucket_suffix.hex}"

  force_destroy = true

  tags = merge(local.tags, {
    Name = "${var.project_name}-alb-logs"
  })
}

# Force destroy S3 bucket (for cleanup)
resource "aws_s3_bucket_ownership_controls" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    object_ownership = "BucketOwnerPreferred"
  }
}

resource "aws_s3_bucket_acl" "alb_logs" {
  depends_on = [aws_s3_bucket_ownership_controls.alb_logs]

  bucket = aws_s3_bucket.alb_logs.id
  acl    = "private"
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "delete_after_1_day"
    status = "Enabled"

    expiration {
      days = 1
    }
  }
}

# S3 Bucket Policy for ALB Access Logs
# Get AWS account ID for bucket policy
data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowALBLogDelivery"
        Effect = "Allow"
        Principal = {
          Service = "logdelivery.elasticloadbalancing.amazonaws.com"
        }
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.alb_logs.arn}/alb-access-logs/*"
      },
      {
        Sid    = "AllowALBBucketAcl"
        Effect = "Allow"
        Principal = {
          Service = "logdelivery.elasticloadbalancing.amazonaws.com"
        }
        Action = [
          "s3:GetBucketAcl"
        ]
        Resource = aws_s3_bucket.alb_logs.arn
      }
    ]
  })

  depends_on = [
    aws_s3_bucket_ownership_controls.alb_logs,
    aws_s3_bucket_acl.alb_logs
  ]
}
