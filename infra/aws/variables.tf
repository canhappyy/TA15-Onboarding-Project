variable "project_name" {
  description = "Name used as a prefix for AWS resources"
  type        = string
  default     = "ta15-onboarding"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either dev or prod."
  }
}

variable "aws_region" {
  description = "AWS region used for deployment"
  type        = string
  default     = "ap-southeast-4"
}

variable "frontend_origins" {
  description = "Origins allowed to call the HTTP API from a browser"
  type        = list(string)

  default = [
    "http://localhost:3000"
  ]
}