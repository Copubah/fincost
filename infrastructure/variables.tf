variable "aws_region" {
  description = "AWS region used for the serverless analyzer resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "dev"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.environment))
    error_message = "environment must contain lowercase letters, numbers, and hyphens only."
  }
}

variable "project_name" {
  description = "Short project identifier used in AWS resource names."
  type        = string
  default     = "s3-storage-optimizer"
}

variable "scan_schedule_expression" {
  description = "EventBridge Scheduler expression for automatic scans."
  type        = string
  default     = "rate(1 day)"
}

variable "lambda_timeout_seconds" {
  description = "Maximum scanner execution time in seconds."
  type        = number
  default     = 60
}

variable "lambda_memory_mb" {
  description = "Memory allocated to the scanner Lambda."
  type        = number
  default     = 256
}

