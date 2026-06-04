# AI Image Recognition

A serverless AI-powered image recognition application built on AWS. Upload an image and instantly identify celebrities or detect objects, scenes, and activities using Amazon Rekognition.

**Live Demo**: [https://rekognition.fozdigitalz.com](https://rekognition.fozdigitalz.com)

## Architecture

![Architecture Diagram](https://github.com/Fidelisesq/image-recognition-app/blob/main/Image-recognition.png)

## Features

- **Celebrity Recognition** — Identify famous people with Wikipedia bios, confidence scores, and external links
- **Object & Scene Detection** — Detect objects, scenes, activities, and concepts with confidence levels
- **Dual Mode** — Switch between celebrity and labels mode via dropdown
- **Recent Analyses** — View thumbnails of previously analyzed images
- **Delete Results** — Remove analysis results with hover-to-reveal delete button
- **Responsive UI** — Mobile-friendly design with modern gradient styling
- **API Ready** — REST API that can be integrated into other platforms

---

## How to Use the App

1. Visit [https://rekognition.fozdigitalz.com](https://rekognition.fozdigitalz.com)
2. Select a recognition mode:
   - **Celebrity Recognition** — for photos of famous people
   - **Object & Scene Detection** — for general image analysis
3. Drag and drop an image (JPEG or PNG, max 5MB) or click to browse
4. Click **Analyze Image**
5. View results on the right panel
6. Browse recent analyses at the bottom

---

## Project Structure

```
image-recognition/
├── .github/workflows/
│   └── deploy.yml              # CI/CD pipeline (Terraform + website deploy)
├── codes/
│   ├── celebrity.py            # Standalone celebrity recognition script
│   ├── celebrity-web.py        # Celebrity recognition (web version)
│   ├── image.py                # Standalone label detection script
│   ├── image-web.py            # Label detection (web version)
│   └── processor-web.py        # Combined processor (deployed to Lambda)
├── terraform/
│   ├── lambda_packages/
│   │   ├── presign/            # Presigned URL generator Lambda
│   │   ├── processor/          # Image processor Lambda (auto-generated)
│   │   └── results/            # Results retrieval Lambda
│   ├── main.tf                 # Main infrastructure definition
│   ├── variables.tf            # Input variables
│   └── outputs.tf              # Output values
├── website/
│   ├── index.html              # Main application page
│   ├── app.js                  # Frontend application logic
│   ├── config.js               # API configuration (auto-injected by CI/CD)
│   ├── styles.css              # Custom styling
│   └── favicon.svg             # App icon
└── README.md
```

---

## Infrastructure

### AWS Services Used

| Service | Purpose |
|---------|---------|
| **S3** | Image storage + static website hosting |
| **Lambda** | Presigned URLs, image processing, results retrieval |
| **API Gateway (HTTP)** | REST API endpoints with throttling |
| **Amazon Rekognition** | Celebrity recognition + label detection |
| **DynamoDB** | Results storage with 7-day TTL |
| **CloudFront** | CDN with custom domain and SSL |
| **Route 53** | DNS routing to CloudFront |
| **ACM** | SSL/TLS certificate |
| **IAM** | Least-privilege Lambda execution role |

### Security

- API Gateway throttling: 20 requests/second, burst 50
- S3 buckets: Private, accessed via CloudFront OAC only
- CORS: Restricted to application domain
- CloudFront: HTTPS enforced, TLS 1.2+
- Presigned URLs: Expire in 5 minutes
- Input validation: Only JPEG/PNG accepted server-side
- DynamoDB TTL: Results auto-deleted after 7 days
- No secrets in code: Sensitive values stored in GitHub Secrets

---

## Deployment

### Prerequisites

- AWS account with the following pre-configured:
  - ACM certificate (in us-east-1)
  - Route 53 hosted zone
  - GitHub OIDC IAM role (`github-platform-actions-oidc`)
  - S3 bucket for Terraform state (`foz-terraform-state-bucket`)
- GitHub repository with these secrets:
  - `CERTIFICATE_ARN` — ACM certificate ARN
  - `HOSTED_ZONE_ID` — Route 53 hosted zone ID

### CI/CD Pipeline

Deployment is fully automated via GitHub Actions:

| Trigger | Action |
|---------|--------|
| Push to `main` | Deploy infrastructure + website |
| Commit message contains "destroy" | Destroy all infrastructure |
| Workflow dispatch → "deploy" | Manual deploy |
| Workflow dispatch → "destroy" | Manual destroy |

The pipeline:
1. Authenticates via OIDC (no stored AWS keys)
2. Runs `terraform apply` to create/update infrastructure
3. Extracts the API Gateway URL from Terraform outputs
4. Injects the URL into `website/config.js`
5. Syncs website files to S3
6. Invalidates CloudFront cache

### Manual Deployment (Optional)

```bash
cd terraform
terraform init
terraform apply -var="certificate_arn=YOUR_CERT_ARN" -var="hosted_zone_id=YOUR_ZONE_ID"

# Deploy website
aws s3 sync ../website s3://$(terraform output -raw website_bucket)/ --delete
aws cloudfront create-invalidation --distribution-id $(terraform output -raw cloudfront_distribution_id) --paths "/*"
```

---

## API Endpoints

**Base URL**: Output from `terraform output api_endpoint`

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/upload` | Get presigned URL for image upload |
| GET | `/results` | List all recognition results |
| GET | `/results/{imageId}` | Get specific result |
| DELETE | `/results/{imageId}` | Delete a result |

### Example Usage

```bash
# Get upload URL
curl -X POST https://YOUR_API/upload \
  -H "Content-Type: application/json" \
  -d '{"filename":"photo.jpg","contentType":"image/jpeg","mode":"celebrity"}'

# Upload image to the returned presigned URL
curl -X PUT "PRESIGNED_URL" -H "Content-Type: image/jpeg" --data-binary @photo.jpg

# Check results
curl https://YOUR_API/results/IMAGE_ID
```

---

## Cost Estimate (100 uploads/day)

| Service | Monthly Cost |
|---------|-------------|
| Rekognition | ~$3.00 |
| Lambda | ~$0.00 (free tier) |
| S3 | ~$0.10 |
| DynamoDB | ~$0.00 |
| CloudFront | ~$0.50 |
| API Gateway | ~$0.04 |
| Route 53 | ~$0.50 |
| **Total** | **~$4-7/month** |

---

## Local Development

To run the standalone Python scripts locally:

```bash
pip install boto3

# Celebrity recognition
python codes/celebrity.py

# Object/scene detection
python codes/image.py
```
