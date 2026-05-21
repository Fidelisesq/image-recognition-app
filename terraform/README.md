# Image Recognition Web Application - Terraform Deployment

This Terraform configuration deploys a complete web application for AI-powered image recognition.

## Architecture

```
                                    ┌─────────────────┐
                                    │   CloudFront    │
                                    │   (CDN + SSL)   │
                                    └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
           ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
           │  S3 Website   │        │  API Gateway  │        │   Route 53    │
           │  (Frontend)   │        │   (REST API)  │        │    (DNS)      │
           └───────────────┘        └───────┬───────┘        └───────────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
                    ▼                       ▼                       ▼
           ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
           │    Lambda     │       │    Lambda     │       │    Lambda     │
           │  (Presign)    │       │  (Processor)  │       │  (Results)    │
           └───────────────┘       └───────┬───────┘       └───────┬───────┘
                    │                      │                       │
                    ▼                      ▼                       ▼
           ┌───────────────┐       ┌───────────────┐       ┌───────────────┐
           │   S3 Images   │       │  Rekognition  │       │   DynamoDB    │
           │   (Storage)   │       │     (AI)      │       │  (Results)    │
           └───────────────┘       └───────────────┘       └───────────────┘
```

## Features

- **Web Interface**: Beautiful, responsive dashboard at rekognition.fozdigitalz.com
- **Drag & Drop Upload**: Easy image upload with preview
- **Presigned URLs**: Secure direct-to-S3 uploads
- **Real-time Results**: Automatic polling for recognition results
- **Result History**: View recent analyses with thumbnails
- **Celebrity Recognition**: Identify famous people with Wikipedia bios
- **Image Labels**: Detect objects, scenes, and activities

## Prerequisites

1. [Terraform](https://www.terraform.io/downloads) installed (v1.0+)
2. AWS CLI configured with credentials
3. Domain with Route53 hosted zone
4. ACM certificate in us-east-1 for CloudFront

## Quick Start

```bash
# 1. Navigate to terraform directory
cd terraform

# 2. Initialize Terraform
terraform init

# 3. Deploy infrastructure
terraform apply

# 4. Update config.js with API endpoint (in website directory)
# (See output: api_endpoint)

# 5. Upload website files (from terraform directory)
aws s3 sync ../website s3://YOUR-WEBSITE-BUCKET/ --delete

# 6. Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR-DIST-ID --paths "/*"
```

## Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `lambda_code_file` | `celebrity-web.py` or `image-web.py` | `celebrity-web.py` |
| `aws_region` | AWS region for resources | `eu-west-2` |
| `domain_name` | Website domain | `rekognition.fozdigitalz.com` |
| `hosted_zone_id` | Route53 hosted zone ID | - |
| `certificate_arn` | ACM certificate ARN (us-east-1) | - |

## Post-Deployment Steps

1. **Update config.js**: Replace `YOUR_API_ENDPOINT_HERE` in `../website/config.js` with the actual API Gateway URL from Terraform output

2. **Upload website** (from terraform directory):
   ```bash
   aws s3 sync ../website s3://$(terraform output -raw website_bucket)/ --delete
   ```

3. **Invalidate cache**:
   ```bash
   aws cloudfront create-invalidation \
     --distribution-id $(terraform output -raw cloudfront_distribution_id) \
     --paths "/*"
   ```

4. **Visit your site**: https://rekognition.fozdigitalz.com

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /upload | Get presigned URL for image upload |
| GET | /results | List all recognition results |
| GET | /results/{imageId} | Get specific result |

## Switching Recognition Modes

```bash
# Celebrity recognition (with Wikipedia bios)
terraform apply -var="lambda_code_file=celebrity-web.py"

# Image label detection
terraform apply -var="lambda_code_file=image-web.py"
```

## Cleanup

```bash
# Destroy all resources
terraform destroy
```

## Cost Estimate

| Service | Estimated Monthly Cost |
|---------|----------------------|
| CloudFront | ~$1-5 (depends on traffic) |
| S3 | ~$0.50 |
| Lambda | ~$0 (free tier) |
| API Gateway | ~$0 (free tier) |
| DynamoDB | ~$0 (on-demand, low usage) |
| Rekognition | ~$1 per 1000 images |
| Route53 | ~$0.50 |

**Total**: ~$3-10/month for moderate usage
