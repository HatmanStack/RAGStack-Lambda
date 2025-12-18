# Deployment Guide

## Prerequisites

- AWS Account with admin access
- AWS CLI configured: `aws sts get-caller-identity`
- Python 3.13+, Node.js 24+, SAM CLI
- **Docker** (required to build Lambda layers)

## Region Requirement

**Currently requires `us-east-1`** - Nova Multimodal Embeddings (used for document/image indexing) is only available in us-east-1. When it becomes available in other regions, simply deploy there with `--region <your-region>`.

## Deploy

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

python publish.py \
  --project-name myapp \
  --admin-email admin@example.com
```

**Flags:**
- `--skip-ui`: Skip UI rebuild (backend only)

## Post-Deployment

1. Check email for temporary password
2. Open CloudFront URL from outputs
3. Sign in and set permanent password
4. Upload test document to verify

## Update Deployment

```bash
git pull origin main

# Update everything
python publish.py --project-name myapp --admin-email admin@example.com

# Update backend only (skip UI)
python publish.py --project-name myapp --admin-email admin@example.com --skip-ui
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

**"Docker not found"** → Ensure Docker is installed and running

**"Insufficient permissions"** → Need admin IAM access

**UI not loading** → Invalidate CloudFront: `aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"`

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more.
