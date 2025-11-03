# Deployment Guide

## Prerequisites

- AWS Account with admin access
- AWS CLI configured: `aws sts get-caller-identity`
- Python 3.13+, Node.js 24+, SAM CLI, Docker
- Bedrock models enabled in AWS Console → Bedrock → Model access:
  - `anthropic.claude-3-5-haiku-20241022-v1:0`
  - `amazon.titan-embed-text-v2:0`
  - `amazon.titan-embed-image-v1`

## Deploy

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# With chat (recommended)
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1 \
  --deploy-chat

# Search only
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1
```

**Flags:**
- `--deploy-chat`: Deploy AI chat with web component
- `--chat-only`: Update chat only (after SAM deployed)
- `--skip-ui`: Skip UI rebuild

## Post-Deployment

1. Check email for temporary password
2. Open CloudFront URL from outputs
3. Sign in and set permanent password
4. Upload test document to verify

## Update Deployment

```bash
git pull origin main

# Update everything
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --deploy-chat

# Update backend only (skip UI)
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --skip-ui

# Update chat only
python publish.py --project-name myapp --admin-email admin@example.com --region us-east-1 --chat-only
```

## Uninstall

```bash
# Empty S3 buckets
aws s3 rm s3://ragstack-myapp-input-<account-id>/ --recursive
aws s3 rm s3://ragstack-myapp-extracted-<account-id>/ --recursive
aws s3 rm s3://ragstack-myapp-vectors-<account-id>/ --recursive

# Delete Knowledge Base
aws bedrock-agent delete-knowledge-base --knowledge-base-id <KB-ID>

# Delete stack
aws cloudformation delete-stack --stack-name RAGStack-myapp
```

## Troubleshooting

**"Resource already exists"** → Change project name

**"Model not enabled"** → Enable Bedrock models in console, wait 5-10 min

**"Insufficient permissions"** → Need admin IAM access

**UI not loading** → Invalidate CloudFront: `aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"`

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more.
