# =============================================================================
# APPLICATION LOAD BALANCER
# =============================================================================

# Application Load Balancer
resource "aws_lb" "app" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection       = false # Allow force destroy
  enable_http2                     = true
  enable_cross_zone_load_balancing = true

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    enabled = true
    prefix  = "alb-access-logs"
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-alb"
  })
}

# Target Group for EC2 instances
resource "aws_lb_target_group" "app" {
  name     = "${local.name_prefix}-tg"
  port     = var.app_port
  protocol = "HTTP"
  vpc_id   = aws_vpc.this.id

  health_check {
    enabled             = true
    healthy_threshold   = 2         # Consecutive successful checks to mark healthy
    unhealthy_threshold = 2         # Consecutive failed checks to mark unhealthy
    timeout             = 5         # Timeout for each health check request (seconds)
    interval            = 30        # Interval between health checks (seconds)
    path                = "/health" # Health check endpoint (FastAPI /health endpoint)
    matcher             = "200"     # HTTP status code that indicates healthy (matches FastAPI endpoint)
    protocol            = "HTTP"
    port                = "traffic-port" # Use same port as traffic (var.app_port)
  }

  deregistration_delay = 30

  tags = merge(local.tags, {
    Name = "${var.project_name}-tg"
  })
}

# ALB Listener (HTTP)
resource "aws_lb_listener" "app" {
  load_balancer_arn = aws_lb.app.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-alb-listener"
  })
}
