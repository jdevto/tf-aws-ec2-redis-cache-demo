# Shopping Cart with EC2 + ElastiCache (Redis)

A complete Terraform implementation of a shopping cart system using EC2 application servers and ElastiCache Redis in a single VPC.

## Architecture

- **VPC**: Single VPC with public and private subnets across multiple availability zones
- **Application Load Balancer**: Public-facing ALB in public subnets, routes to EC2 instances
- **EC2 Auto Scaling Group**: Application servers in private subnets running FastAPI (Python 3)
- **ElastiCache Redis**: Multi-AZ Redis cluster in private subnets for cart caching
- **S3 Bucket**: Application code storage - Terraform automatically uploads app files
- **Security Groups**: Least-privilege rules (app can only reach Redis on 6379)
- **CloudWatch**: Dashboards and alarms for observability
- **Secrets Manager**: Secure storage for Redis authentication token

## Features

- ✅ Atomic cart operations using Lua scripts with proper error handling
- ✅ Multi-AZ Redis replication with automatic failover
- ✅ Force destroy enabled on all resources
- ✅ CloudWatch logging with 1-day retention
- ✅ Least-privilege IAM permissions with separate read/write SIDs
- ✅ Frontend demo application demonstrating Redis caching with instance ID display
- ✅ Cart merge functionality for guest-to-user conversion
- ✅ Health checks and retry logic with Redis connection pooling
- ✅ Robust error handling for Redis script execution issues

## Prerequisites

- Terraform >= 1.0
- AWS CLI configured with appropriate credentials
- AWS account with permissions to create:
  - VPC, subnets, security groups
  - EC2 instances and Auto Scaling Groups
  - ElastiCache Redis clusters
  - Application Load Balancers
  - S3 buckets and objects (for application code)
  - IAM roles and policies
  - Secrets Manager secrets
  - CloudWatch dashboards and alarms

## Deployment

### 1. Configure Variables

Edit `variables.tf` or create a `terraform.tfvars` file:

```hcl
project_name = "my-cart-demo"
availability_zones = ["ap-southeast-2a", "ap-southeast-2b"]

# EC2 configuration
ec2_instance_type = "t3.micro"
min_size = 1
max_size = 3
desired_capacity = 2

# Redis configuration
redis_node_type = "cache.t3.micro"
redis_num_cache_nodes = 2
```

**Note**: The AWS region is automatically determined from your AWS provider configuration (AWS CLI config, environment variables, or provider block in `versions.tf`).

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Apply Infrastructure

```bash
terraform apply
```

### 5. Access Application

After deployment, get the ALB URL:

```bash
terraform output alb_url
```

Open the URL in your browser to access the shopping cart demo.

## Application Deployment

**Automatic Deployment**: Application files are automatically deployed via S3:

1. **Terraform uploads** all files from `app/` directory to S3 during `terraform apply`
2. **EC2 user data script** automatically downloads files from S3 on instance boot
3. **No manual steps required** - everything is handled by Terraform

The S3 bucket name is available in outputs:

```bash
terraform output app_code_bucket
```

**How it works**:

- Terraform reads all application files from `app/` directory
- Files are uploaded to S3 bucket with encryption and versioning enabled
- EC2 instances download from S3 during boot (user_data.sh runs `aws s3 sync`)
- Application starts automatically after download
- **To update code**: Run `terraform apply -target=aws_s3_object.app_files`, then trigger instance refresh

## API Endpoints

- `GET /health` - Health check
- `POST /cart/items` - Add/update cart item
- `GET /cart` - Get cart contents
- `DELETE /cart/items/{productId}` - Remove item from cart
- `POST /cart/merge` - Merge two carts
- `POST /checkout/start` - Start checkout process

All cart operations require `X-Cart-ID` header. Optional `X-User-ID` header for logged-in users.

## Testing Redis Cache

1. **Add items to cart** - See sub-millisecond latency from Redis
2. **Open multiple browser tabs** with the same cart ID to see shared state across instances
3. **Watch response times** - Each API call shows Redis latency
4. **View instance ID** - Frontend displays which EC2 instance served the request (load balancing demo)
5. **Switch between users** - Separate cart namespaces in Redis
6. **Merge carts** - Demonstrate atomic Redis operations

## Monitoring

### CloudWatch Dashboards

- Redis Dashboard: CPU, memory, evictions, connections, hit/miss rates
- Application Dashboard: Cart operations, latency, errors

Access dashboards via Terraform outputs:

```bash
terraform output cloudwatch_dashboard_redis
terraform output cloudwatch_dashboard_app
```

### Alarms

- Redis high memory usage (>80%)
- Redis high CPU usage (>80%)
- Redis replication lag

## Security

- All resources in private subnets (no public IPs on EC2)
- EC2 access via AWS Systems Manager Session Manager (no SSH keys required)
- Security groups: app-sg → redis-sg on port 6379 only
- Redis authentication enabled
- IAM roles with least-privilege permissions (separate read/write SIDs)
- SSM managed instance core policy attached for Session Manager access
- No PII in logs (cart IDs are hashed)

## Cost Optimization

- App and Redis primary node placed in same AZ to reduce cross-AZ data transfer
- Use smallest instance types for demo (t3.micro)
- All resources configured for easy cleanup (force destroy enabled)
- CloudWatch log retention: 1 day

## Cleanup

To destroy all resources:

```bash
terraform destroy
```

All resources are configured with `deletion_protection = false` and force destroy enabled.

## File Structure

```text
.
├── main.tf                 # VPC and networking
├── variables.tf            # Input variables
├── outputs.tf              # Output values
├── locals.tf               # Local values
├── versions.tf             # Provider versions
├── security_groups.tf      # Security groups
├── iam.tf                  # IAM roles and policies
├── secrets.tf              # Secrets Manager
├── elasticache.tf          # ElastiCache Redis
├── ec2.tf                  # EC2 Auto Scaling Group
├── alb.tf                  # Application Load Balancer
├── cloudwatch.tf           # CloudWatch dashboards and alarms
├── s3.tf                   # S3 bucket for application code
├── user_data.tf            # User data template
├── user_data.sh            # EC2 initialization script
├── app/                    # FastAPI application (automatically deployed to S3)
│   ├── main.py             # FastAPI app entry point
│   ├── config.py           # Configuration
│   ├── redis_client.py      # Redis client wrapper
│   ├── models.py            # Pydantic models
│   ├── cart_service.py     # Cart business logic
│   ├── checkout_service.py # Checkout service
│   ├── atomic_scripts.py   # Lua scripts
│   ├── middleware.py       # Metrics and logging
│   ├── exceptions.py       # Custom exceptions
│   ├── requirements.txt    # Python dependencies
│   └── static/
│       └── index.html      # Frontend demo UI
└── README.md               # This file
```

## Troubleshooting

### Application not starting

1. Connect to EC2 instance via SSM Session Manager:

   ```bash
   aws ssm start-session --target <instance-id>
   ```

2. Check EC2 instance logs: `sudo journalctl -u cart-app -f`
3. Check user data logs: `cat /var/log/user-data.log`
4. Verify application files were downloaded from S3: `ls -la /opt/cart-app/app/`
5. Check S3 bucket access: Verify IAM role has S3 read permissions
6. Verify Redis endpoint is accessible from EC2
7. Check security groups allow app → Redis on 6379
8. Verify Secrets Manager access from EC2 IAM role

### Accessing EC2 Instances

EC2 instances are accessible via AWS Systems Manager Session Manager (no SSH required):

1. **Get instance ID**:

   ```bash
   aws ec2 describe-instances --filters "Name=tag:Name,Values=${project_name}*" --query "Reservations[*].Instances[*].[InstanceId,State.Name]" --output table
   ```

2. **Connect via SSM**:

   ```bash
   aws ssm start-session --target <instance-id>
   ```

3. **Or use AWS Console**: EC2 → Instances → Select instance → Connect → Session Manager tab

### Redis connection errors

1. Verify Redis cluster is in "available" state
2. Check security group rules (app-sg → redis-sg)
3. Verify Redis auth token in Secrets Manager
4. Check Redis endpoint in application logs
5. **Empty list errors**: If seeing "Redis script returned empty list", the fix handles this by checking Redis directly - ensure latest code is deployed

### ALB health checks failing

1. Verify EC2 instances are running
2. Check security group allows ALB → EC2 on app port
3. Verify application is listening on correct port
4. Check application health endpoint: `curl http://localhost:8000/health`

## License

See LICENSE file for details.
