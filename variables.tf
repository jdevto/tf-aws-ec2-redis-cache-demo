variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "ec2-redis-cache-demo"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["ap-southeast-2a", "ap-southeast-2b"]
}

variable "one_nat_gateway_per_az" {
  description = "Should be true if you want one NAT Gateway per availability zone. Otherwise, one NAT Gateway will be used for all AZs."
  type        = bool
  default     = false
}

variable "app_port" {
  description = "Port for the FastAPI application"
  type        = number
  default     = 8000
}

variable "redis_node_type" {
  description = "ElastiCache Redis node instance type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_cache_nodes" {
  description = "Number of cache nodes in Redis replication group"
  type        = number
  default     = 2
}

variable "ec2_instance_type" {
  description = "EC2 instance type for application servers"
  type        = string
  default     = "t3.micro"
}

variable "min_size" {
  description = "Minimum number of EC2 instances in Auto Scaling Group"
  type        = number
  default     = 1
}

variable "max_size" {
  description = "Maximum number of EC2 instances in Auto Scaling Group"
  type        = number
  default     = 3
}

variable "desired_capacity" {
  description = "Desired number of EC2 instances in Auto Scaling Group"
  type        = number
  default     = 2
}

variable "cart_ttl_days" {
  description = "TTL for cart keys in days"
  type        = number
  default     = 7
}
