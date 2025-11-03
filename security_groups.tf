# =============================================================================
# SECURITY GROUPS
# =============================================================================

# Security Group for Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb-sg"
  description = "Security group for Application Load Balancer"
  vpc_id      = aws_vpc.this.id

  ingress {
    description = "HTTP from user public IP only"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["${trimspace(data.http.my_public_ip.response_body)}/32"]
  }

  ingress {
    description = "HTTPS from user public IP only"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["${trimspace(data.http.my_public_ip.response_body)}/32"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-alb-sg"
  })
}

# Security Group for EC2 Application Instances
resource "aws_security_group" "app" {
  name        = "${var.project_name}-app-sg"
  description = "Security group for EC2 application instances"
  vpc_id      = aws_vpc.this.id

  ingress {
    description     = "Allow traffic from ALB on app port"
    from_port       = var.app_port
    to_port         = var.app_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "Allow HTTPS outbound for AWS services"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow HTTP outbound for package installation"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound TCP (for Redis and other services)"
    from_port   = 0
    to_port     = 65535
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${var.project_name}-app-sg"
  })
}

# Security Group for ElastiCache Redis
resource "aws_security_group" "redis" {
  name        = "${var.project_name}-redis-sg"
  description = "Security group for ElastiCache Redis"
  vpc_id      = aws_vpc.this.id

  # No egress needed for Redis security group

  tags = merge(local.tags, {
    Name = "${var.project_name}-redis-sg"
  })
}

# Separate security group rule to avoid circular dependency
resource "aws_security_group_rule" "redis_ingress_from_app" {
  type                     = "ingress"
  from_port                = 6379
  to_port                  = 6379
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.app.id
  security_group_id        = aws_security_group.redis.id
  description              = "Allow Redis from app security group only"
}
