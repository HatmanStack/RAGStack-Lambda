# Deployment Guide

## Prerequisites

- AWS Account with admin access
- AWS CLI configured: `aws sts get-caller-identity`
- Python 3.13+, Node.js 24+, SAM CLI
- **Docker** (required to build Lambda layers)
- **For chat (optional):** Amplify CLI (auto-installed if missing)

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

# Without chat
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1
```

**Flags:**
- `--deploy-chat`: Deploy AI chat with web component (requires Amplify CLI)
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

# Delete Amplify app (if chat deployed)
amplify delete
```

## Troubleshooting

**"Resource already exists"** → Change project name

**"Docker not found"** → Ensure Docker is installed and running

**"Amplify CLI installation failed"** → Ensure npm/Node.js is installed and npm can write to global package directory

**"Insufficient permissions"** → Need admin IAM access

**UI not loading** → Invalidate CloudFront: `aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"`

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more.
