variable "aws_region" {
  description = "AWS region for main resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "rekognition-web"
}

variable "domain_name" {
  description = "Domain name for the web application"
  type        = string
  default     = "rekognition.fozdigitalz.com"
}

variable "hosted_zone_id" {
  description = "Route53 hosted zone ID"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN (must be in us-east-1 for CloudFront)"
  type        = string
}

variable "lambda_code_file" {
  description = "The Lambda code file to deploy for the processor"
  type        = string
  default     = "processor-web.py"
}

variable "lambda_timeout" {
  description = "Lambda function timeout in seconds"
  type        = number
  default     = 30
}

variable "lambda_memory" {
  description = "Lambda function memory in MB"
  type        = number
  default     = 256
}
