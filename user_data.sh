#!/bin/bash
set -euo pipefail

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting user data script execution..."

# Get metadata from IMDS (Instance Metadata Service)
echo "Fetching instance metadata from IMDS..."
IMDS_TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" || echo "")

# Get region from IMDS (prefer IMDSv2, fallback to IMDSv1)
if [ -n "$IMDS_TOKEN" ]; then
    # Use IMDSv2 (token-based, more secure)
    AWS_REGION=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/placement/region" || echo "${region}")
    AVAILABILITY_ZONE=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/placement/availability-zone" || echo "")
    INSTANCE_ID=$(curl -s -H "X-aws-ec2-metadata-token: $IMDS_TOKEN" "http://169.254.169.254/latest/meta-data/instance-id" || echo "")
else
    # Fallback to IMDSv1
    AWS_REGION=$(curl -s "http://169.254.169.254/latest/meta-data/placement/region" || echo "${region}")
    AVAILABILITY_ZONE=$(curl -s "http://169.254.169.254/latest/meta-data/placement/availability-zone" || echo "")
    INSTANCE_ID=$(curl -s "http://169.254.169.254/latest/meta-data/instance-id" || echo "")
fi

echo "Instance metadata retrieved:"
echo "  Region: $AWS_REGION"
echo "  Availability Zone: $AVAILABILITY_ZONE"
echo "  Instance ID: $INSTANCE_ID"

# Export region for AWS CLI (uses IMDS credentials automatically via IAM role)
export AWS_DEFAULT_REGION=$AWS_REGION
export AWS_REGION=$AWS_REGION

# Install Python 3.13 via package manager
echo "Updating system packages..."
yum update -y

# Install Python 3.13 and pip (Amazon Linux 2023 may have Python 3.11+)
echo "Installing Python and dependencies..."
yum install -y python3 python3-pip python3-devel tar gzip curl-minimal unzip

# Verify Python installation
echo "Verifying Python installation..."
python3 --version || {
    echo "ERROR: Python installation failed"
    exit 1
}
python3 -m pip --version || {
    echo "ERROR: pip installation failed"
    exit 1
}
echo "Python installed successfully via package manager."

# Create application directory
echo "Creating application directory structure..."
mkdir -p /opt/cart-app
cd /opt/cart-app

# Create application structure
mkdir -p app/static

# Install AWS CLI v2 (needed for S3 download and Secrets Manager)
echo "Installing AWS CLI v2..."
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
if [ $? -eq 0 ]; then
    unzip -q awscliv2.zip
    ./aws/install
    rm -rf aws awscliv2.zip
    echo "AWS CLI v2 installed successfully"
else
    echo "Failed to download AWS CLI v2, falling back to yum install"
    yum install -y awscli
fi

# Download application files from S3
echo "Downloading application files from S3 bucket: ${app_code_bucket}..."
aws s3 sync s3://${app_code_bucket}/app/ /opt/cart-app/app/ --delete
echo "Application files downloaded successfully."

# Install application dependencies
echo "Installing Python dependencies..."
python3 -m pip install -r /opt/cart-app/app/requirements.txt
echo "Python dependencies installed successfully."

# Fetch Redis authentication token from Secrets Manager
# AWS CLI automatically uses IMDS for credentials via IAM instance profile
echo "Fetching Redis credentials from Secrets Manager (using IMDS credentials)..."
SECRET_VALUE=$(aws secretsmanager get-secret-value --secret-id ${redis_secret_name} --query SecretString --output text)
REDIS_AUTH=$(echo $SECRET_VALUE | python3 -c "import sys, json; print(json.load(sys.stdin)['auth_token'])")
REDIS_ENDPOINT=$(echo $SECRET_VALUE | python3 -c "import sys, json; print(json.load(sys.stdin).get('endpoint', '${redis_endpoint}'))" 2>/dev/null || echo "${redis_endpoint}")
echo "Redis credentials retrieved successfully."

# Create environment file for application
echo "Creating application environment file..."
cat > /opt/cart-app/.env << EOF
REDIS_HOST=$REDIS_ENDPOINT
REDIS_PORT=6379
REDIS_AUTH_TOKEN=$REDIS_AUTH
REDIS_SECRET_NAME=${redis_secret_name}
APP_PORT=${app_port}
PROJECT_NAME=${project_name}
REGION=$AWS_REGION
EOF

# Create systemd service
echo "Creating systemd service for cart-app..."
cat > /etc/systemd/system/cart-app.service << EOF
[Unit]
Description=Shopping Cart FastAPI Application
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/cart-app
EnvironmentFile=/opt/cart-app/.env
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port ${app_port}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Start the service
echo "Starting cart-app service..."
systemctl daemon-reload
systemctl enable cart-app
systemctl start cart-app

# Verify service status
echo "Checking service status..."
sleep 2
systemctl status cart-app --no-pager || true

echo "User data script execution completed successfully."
echo "Cart application service configured on port ${app_port}"
echo "Service logs available at: journalctl -u cart-app -f"
