# Deployment Guide

Deploy RAGStack-Lambda to your AWS account in 3 steps (~1 hour).

## Prerequisites

### Checklist

- ✅ AWS Account with admin access
- ✅ AWS CLI configured: `aws sts get-caller-identity`
- ✅ Python 3.13+: `python3.13 --version`
- ✅ Node.js 24+: `node --version`
- ✅ SAM CLI: `sam --version` (install: `brew install aws-sam-cli`)
- ✅ Docker running: `docker ps`
- ✅ Git: `git --version`

### Enable Bedrock Models

**Required before deployment!**

1. Go to AWS Console → Bedrock → Model access
2. Enable these models:
   - `anthropic.claude-3-5-haiku-20241022-v1:0`
   - `amazon.titan-embed-text-v2:0`
   - `amazon.titan-embed-image-v1`
3. Wait 5-10 minutes for approval

### Check Service Quotas

AWS Console → Service Quotas, verify:

| Service | Current Quota | Minimum Needed |
|---------|---------------|-----------------|
| Lambda concurrent executions | View | 100 |
| Textract concurrent requests | View | 20 |
| S3 buckets | View | 5 available |
| DynamoDB tables | View | 2 available |

Request quota increase if needed (takes 1-2 hours).

## Deployment Steps

### Step 1: Clone & Setup

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda

# Install dependencies
npm install
cd src/ui && npm install && cd ../..
```

### Step 2: Deploy Stack

```bash
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1
```

**Parameters**:
- `--project-name`: lowercase, alphanumeric + hyphens, 2-32 chars (used for all resource names)
- `--admin-email`: valid email (receives temporary password)
- `--region`: AWS region (us-east-1, us-west-2, eu-west-1, etc.)
- `--skip-ui` (optional): skip UI build if only updating backend

**What happens:**
1. Validates prerequisites (5 min)
2. Builds Lambda functions via SAM (10 min)
3. Deploys CloudFormation stack (15 min)
4. Builds React UI via CodeBuild (10 min)
5. Configures Bedrock Knowledge Base (5 min)
6. **Total: ~45-60 minutes**

### Step 3: Monitor Deployment

```bash
# Watch CloudFormation stack creation
aws cloudformation describe-stacks \
  --stack-name RAGStack-myapp \
  --query 'Stacks[0].StackStatus' \
  --output text

# Expected: CREATE_IN_PROGRESS → CREATE_COMPLETE
```

Check AWS Console → CloudFormation → Events for details if deployment fails.

### Step 4: Get Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name RAGStack-myapp \
  --query 'Stacks[0].Outputs' \
  --output table
```

**Important outputs**:
- `WebUIUrl` - CloudFront URL for web interface
- `BedrockKbId` - Knowledge Base ID (save for chat setup)
- `QueryKbLambdaArn` - Lambda ARN (save for chat setup)

## Post-Deployment

### First Login

1. Check email for temporary password
2. Open `WebUIUrl` in browser
3. Enter email + temporary password
4. Set permanent password (8+ chars: upper, lower, number, special char)
5. Welcome! Now on Dashboard

### Verify Setup

1. **Can login?** ✅
2. **Can upload documents?** Upload a test PDF via Upload page
3. **Can search?** Search for text from uploaded document

If any step fails, check [Troubleshooting Guide](TROUBLESHOOTING.md).

## Updating Deployment

### Backend Changes

```bash
# Update code
git pull origin main

# Rebuild and redeploy (skip UI if UI didn't change)
python publish.py \
  --project-name myapp \
  --admin-email admin@example.com \
  --region us-east-1 \
  --skip-ui
```

### Frontend Changes

Same as backend (publish.py handles UI rebuild).

### Configuration Changes

No redeployment needed. Modify settings:
1. WebUI Settings page, OR
2. AWS CLI → DynamoDB configuration table

Changes apply immediately.

### Monitor Updates

```bash
aws logs tail /aws/lambda/RAGStack-myapp-ProcessDocument --follow
```

## Uninstalling

**Caution**: This deletes everything (documents, config, stack).

```bash
# 1. Empty S3 buckets
aws s3 rm s3://ragstack-myapp-input-<account-id>/ --recursive
aws s3 rm s3://ragstack-myapp-extracted-<account-id>/ --recursive
aws s3 rm s3://ragstack-myapp-vectors-<account-id>/ --recursive

# 2. Delete Bedrock Knowledge Base
aws bedrock-agent delete-knowledge-base --knowledge-base-id <KB-ID>

# 3. Delete CloudFormation stack
aws cloudformation delete-stack --stack-name RAGStack-myapp

# 4. Delete Parameter Store values
aws ssm delete-parameter --name /ragstack/myapp/kb-id 2>/dev/null || true
aws ssm delete-parameter --name /ragstack/myapp/query-lambda-arn 2>/dev/null || true

# 5. Verify deletion
aws cloudformation describe-stacks --stack-name RAGStack-myapp
# Should return: Stack with id RAGStack-myapp does not exist
```

## Costs

**Estimated monthly cost** for ~1000 documents/month (5 pages each):

| Service | Cost |
|---------|------|
| Textract + Embeddings | $5-15 |
| S3 + Lambda + DynamoDB | $2 |
| CloudFront + Bedrock | $0.50 |
| **Total** | **~$7-18/month** |

(Using Bedrock OCR instead: ~$25-75/month)

## Troubleshooting

### Deployment Fails

1. **"Resource already exists"** → Change project name
2. **"Model not enabled"** → Enable Bedrock models (wait 5-10 min)
3. **"Insufficient permissions"** → Ensure admin IAM access
4. **"Docker error"** → Start Docker and retry

See [Troubleshooting Guide](TROUBLESHOOTING.md) for more.

### Can't Login

- ✅ Check temporary password email
- ✅ Try password reset on login page
- ✅ Verify Cognito user pool exists

### UI Not Loading

- ✅ Check CloudFront URL is correct
- ✅ Clear browser cache
- ✅ Invalidate CloudFront:
  ```bash
  aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"
  ```

## Next Steps

1. ✅ Verify deployment (login, upload, search)
2. ✅ Read [User Guide](USER_GUIDE.md) to learn features
3. ✅ Upload real documents
4. ✅ Customize [Configuration](CONFIGURATION.md) if needed
5. ✅ Optional: Deploy [chat component](AMPLIFY_CHAT.md)

## Support

- **Deployment issues**: [Troubleshooting](TROUBLESHOOTING.md)
- **Architecture questions**: [Architecture](ARCHITECTURE.md)
- **Usage questions**: [User Guide](USER_GUIDE.md)
