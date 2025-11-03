locals {
  tags = {
    Project     = var.project_name
    Environment = "dev"
    ManagedBy   = "terraform"
  }

  # Shortened names for resources with length restrictions
  name_prefix = substr(var.project_name, 0, 20) # Max 20 chars for resource naming
}
