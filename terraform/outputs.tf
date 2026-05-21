output "website_url" {
  description = "Website URL"
  value       = "https://${var.domain_name}"
}

output "api_endpoint" {
  description = "API Gateway endpoint"
  value       = aws_apigatewayv2_api.api.api_endpoint
}

output "images_bucket" {
  description = "S3 bucket for image uploads"
  value       = aws_s3_bucket.images.id
}

output "website_bucket" {
  description = "S3 bucket for website files"
  value       = aws_s3_bucket.website.id
}

output "dynamodb_table" {
  description = "DynamoDB table for results"
  value       = aws_dynamodb_table.results.name
}

output "api_keys_table" {
  description = "DynamoDB table for API keys"
  value       = aws_dynamodb_table.api_keys.name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID"
  value       = aws_cloudfront_distribution.website.id
}

output "upload_website_command" {
  description = "Command to upload website files"
  value       = "aws s3 sync ../website s3://${aws_s3_bucket.website.id}/ --delete"
}

output "invalidate_cache_command" {
  description = "Command to invalidate CloudFront cache"
  value       = "aws cloudfront create-invalidation --distribution-id ${aws_cloudfront_distribution.website.id} --paths '/*'"
}

output "config_js_update" {
  description = "Update config.js API_ENDPOINT with this value"
  value       = "API_ENDPOINT: '${aws_apigatewayv2_api.api.api_endpoint}'"
}

output "api_key_management" {
  description = "API key management endpoints"
  value       = <<-EOT
    Create API Key:  curl -X POST ${aws_apigatewayv2_api.api.api_endpoint}/api-keys -H "x-admin-secret: YOUR_ADMIN_SECRET" -H "Content-Type: application/json" -d '{"owner":"client-name","description":"API key for client"}'
    List API Keys:   curl ${aws_apigatewayv2_api.api.api_endpoint}/api-keys -H "x-admin-secret: YOUR_ADMIN_SECRET"
    Revoke API Key:  curl -X DELETE ${aws_apigatewayv2_api.api.api_endpoint}/api-keys/KEY_ID -H "x-admin-secret: YOUR_ADMIN_SECRET"
  EOT
}

output "api_documentation" {
  description = "API documentation location"
  value       = "See docs/API.md and docs/openapi.yaml for API documentation"
}
