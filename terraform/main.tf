terraform {
  required_version = ">= 1.0"

  backend "s3" {
    bucket = "fozdigitalz-terraform-state"
    key    = "image-recognition/terraform.tfstate"
    region = "eu-west-2"
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# Main provider for eu-west-2
provider "aws" {
  region = var.aws_region
}

# Provider for us-east-1 (required for CloudFront)
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Random suffix for unique bucket names
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# ============================================
# DynamoDB Table for Results
# ============================================
resource "aws_dynamodb_table" "results" {
  name         = "${var.project_name}-results"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "imageId"

  attribute {
    name = "imageId"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = {
    Name    = "${var.project_name}-results"
    Project = var.project_name
  }
}

# ============================================
# S3 Bucket for Image Uploads
# ============================================
resource "aws_s3_bucket" "images" {
  bucket        = "${var.project_name}-images-${random_id.bucket_suffix.hex}"
  force_destroy = true

  tags = {
    Name    = "${var.project_name}-images"
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "images" {
  bucket = aws_s3_bucket.images.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_cors_configuration" "images" {
  bucket = aws_s3_bucket.images.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "HEAD"]
    allowed_origins = ["https://${var.domain_name}", "http://localhost:*"]
    expose_headers  = ["ETag", "x-amz-server-side-encryption", "x-amz-request-id", "x-amz-id-2"]
    max_age_seconds = 3000
  }
}

# ============================================
# S3 Bucket for Static Website
# ============================================
resource "aws_s3_bucket" "website" {
  bucket        = "${var.project_name}-website-${random_id.bucket_suffix.hex}"
  force_destroy = true

  tags = {
    Name    = "${var.project_name}-website"
    Project = var.project_name
  }
}

resource "aws_s3_bucket_public_access_block" "website" {
  bucket = aws_s3_bucket.website.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_website_configuration" "website" {
  bucket = aws_s3_bucket.website.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

resource "aws_s3_bucket_policy" "website" {
  bucket = aws_s3_bucket.website.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontAccess"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.website.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.website.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.website]
}

# ============================================
# IAM Role for Lambda Functions
# ============================================
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name    = "${var.project_name}-lambda-role"
    Project = var.project_name
  }
}

# Custom policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.images.arn}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "rekognition:DetectLabels",
          "rekognition:RecognizeCelebrities"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.results.arn
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# ============================================
# Lambda: Image Processor (S3 triggered)
# ============================================
resource "local_file" "processor_code" {
  content  = file("${path.module}/../codes/${var.lambda_code_file}")
  filename = "${path.module}/lambda_packages/processor/lambda_function.py"
}

data "archive_file" "processor_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_packages/processor"
  output_path = "${path.module}/processor.zip"

  depends_on = [local_file.processor_code]
}

resource "aws_lambda_function" "processor" {
  filename         = data.archive_file.processor_zip.output_path
  function_name    = "${var.project_name}-processor"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.processor_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = var.lambda_timeout
  memory_size      = var.lambda_memory

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.results.name
    }
  }

  tags = {
    Name    = "${var.project_name}-processor"
    Project = var.project_name
  }
}

# S3 trigger for processor
resource "aws_lambda_permission" "s3_trigger" {
  statement_id   = "AllowS3Invoke"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.processor.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = aws_s3_bucket.images.arn
  source_account = data.aws_caller_identity.current.account_id
}

resource "aws_s3_bucket_notification" "images" {
  bucket = aws_s3_bucket.images.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.processor.arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.s3_trigger]
}

# ============================================
# Lambda: Presign URL Generator
# ============================================
data "archive_file" "presign_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_packages/presign"
  output_path = "${path.module}/presign.zip"
}

resource "aws_lambda_function" "presign" {
  filename         = data.archive_file.presign_zip.output_path
  function_name    = "${var.project_name}-presign"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.presign_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      BUCKET_NAME = aws_s3_bucket.images.id
    }
  }

  tags = {
    Name    = "${var.project_name}-presign"
    Project = var.project_name
  }
}

# ============================================
# Lambda: Get Results
# ============================================
data "archive_file" "results_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_packages/results"
  output_path = "${path.module}/results.zip"
}

resource "aws_lambda_function" "results" {
  filename         = data.archive_file.results_zip.output_path
  function_name    = "${var.project_name}-results"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = data.archive_file.results_zip.output_base64sha256
  runtime          = "python3.11"
  timeout          = 10
  memory_size      = 128

  environment {
    variables = {
      DYNAMODB_TABLE = aws_dynamodb_table.results.name
      BUCKET_NAME    = aws_s3_bucket.images.id
    }
  }

  tags = {
    Name    = "${var.project_name}-results"
    Project = var.project_name
  }
}

# ============================================
# API Gateway
# ============================================
resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project_name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["https://${var.domain_name}", "http://localhost:3000", "http://localhost:5500"]
    allow_methods = ["GET", "POST", "DELETE", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 300
  }

  tags = {
    Name    = "${var.project_name}-api"
    Project = var.project_name
  }
}

resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true

  tags = {
    Name    = "${var.project_name}-api-stage"
    Project = var.project_name
  }
}

# Presign endpoint
resource "aws_apigatewayv2_integration" "presign" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.presign.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "presign" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /upload"
  target    = "integrations/${aws_apigatewayv2_integration.presign.id}"
}

resource "aws_lambda_permission" "presign_api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.presign.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# Results endpoint - GET all
resource "aws_apigatewayv2_integration" "results" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.results.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "results_list" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /results"
  target    = "integrations/${aws_apigatewayv2_integration.results.id}"
}

resource "aws_apigatewayv2_route" "results_get" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /results/{imageId}"
  target    = "integrations/${aws_apigatewayv2_integration.results.id}"
}

resource "aws_apigatewayv2_route" "results_delete" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "DELETE /results/{imageId}"
  target    = "integrations/${aws_apigatewayv2_integration.results.id}"
}

resource "aws_lambda_permission" "results_api" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.results.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# ============================================
# CloudFront Distribution
# ============================================
resource "aws_cloudfront_origin_access_control" "website" {
  name                              = "${var.project_name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "website" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.domain_name]
  price_class         = "PriceClass_100"

  origin {
    domain_name              = aws_s3_bucket.website.bucket_regional_domain_name
    origin_id                = "S3-Website"
    origin_access_control_id = aws_cloudfront_origin_access_control.website.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-Website"
    viewer_protocol_policy = "redirect-to-https"

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    acm_certificate_arn      = var.certificate_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }

  tags = {
    Name    = "${var.project_name}-cdn"
    Project = var.project_name
  }
}

# ============================================
# Route53 DNS Record
# ============================================
resource "aws_route53_record" "website" {
  zone_id = var.hosted_zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.website.domain_name
    zone_id                = aws_cloudfront_distribution.website.hosted_zone_id
    evaluate_target_health = false
  }
}
