# =============================================================================
# IAM ROLES AND POLICIES
# =============================================================================

resource "aws_iam_role" "vpc_flow_log" {
  name = "${var.project_name}-vpc-flow-log-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowVPCFlowLogsAssumeRole"
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.tags, {
    Name = "${var.project_name}-vpc-flow-log-role"
  })
}

resource "aws_iam_role_policy" "vpc_flow_log" {
  name = "${var.project_name}-vpc-flow-log-policy"
  role = aws_iam_role.vpc_flow_log.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteVPCFlowLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = aws_cloudwatch_log_group.vpc_flow_logs.arn
      }
    ]
  })
}

# IAM Role for EC2 Instances
resource "aws_iam_role" "ec2_app" {
  name = "${var.project_name}-ec2-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEC2AssumeRole"
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.tags, {
    Name = "${var.project_name}-ec2-app-role"
  })
}

# IAM Policy for EC2 with least-privilege permissions
resource "aws_iam_role_policy" "ec2_app" {
  name = "${var.project_name}-ec2-app-policy"
  role = aws_iam_role.ec2_app.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadSecretsManager"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.redis_auth.arn
        ]
      },
      {
        Sid    = "ReadCloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics"
        ]
        Resource = "*"
      },
      {
        Sid    = "ReadCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams",
          "logs:GetLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.region}:*:log-group:/aws/ec2/${var.project_name}*",
          "arn:aws:logs:${data.aws_region.current.region}:*:log-group:/aws/elasticache/${var.project_name}*"
        ]
      },
      {
        Sid    = "WriteCloudWatchMetrics"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "cloudwatch:namespace" = "${var.project_name}/cart"
          }
        }
      },
      {
        Sid    = "WriteCloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          "arn:aws:logs:${data.aws_region.current.region}:*:log-group:/aws/ec2/${var.project_name}*",
          "arn:aws:logs:${data.aws_region.current.region}:*:log-stream:/aws/ec2/${var.project_name}*"
        ]
      },
      {
        Sid    = "ReadS3AppCode"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.app_code.arn,
          "${aws_s3_bucket.app_code.arn}/*"
        ]
      }
    ]
  })
}

# Attach SSM Managed Instance Core policy for Session Manager access
resource "aws_iam_role_policy_attachment" "ec2_ssm" {
  role       = aws_iam_role.ec2_app.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# IAM Instance Profile for EC2
resource "aws_iam_instance_profile" "ec2_app" {
  name = "${var.project_name}-ec2-app-profile"
  role = aws_iam_role.ec2_app.name

  tags = merge(local.tags, {
    Name = "${var.project_name}-ec2-app-profile"
  })
}
