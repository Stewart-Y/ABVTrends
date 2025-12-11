# ABVTrends Terraform Variables - Minimal Setup

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

# Database
variable "db_username" {
  description = "Database username"
  type        = string
  default     = "abvtrends"
  sensitive   = true
}

variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
}
