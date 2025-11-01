# RAGStack-Lambda Deployment Guide

This guide covers how to deploy RAGStack-Lambda to your AWS account.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Deployment Steps](#deployment-steps)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [First Login](#first-login)
- [Updating an Existing Deployment](#updating-an-existing-deployment)
- [Uninstalling](#uninstalling)

---

## Prerequisites

### AWS Account Requirements

Before deploying, ensure you have:

1. **AWS Account** with administrator access or equivalent permissions
2. **AWS CLI** configured with valid credentials
3. **Bedrock Model Access** - Enable these models in AWS Console:
   - Go to **AWS Console → Bedrock → Model access**
   - Enable the following models:
     - `anthropic.claude-3-5-haiku-20241022-v1:0` (for OCR)
     - `amazon.titan-embed-text-v2:0` (for text embeddings)
     - `amazon.titan-embed-image-v1` (for image embeddings)
   - **Note**: Model access approval can take 5-10 minutes

4. **Service Quotas** - Verify you have sufficient limits:

   | Service | Quota | Recommended Minimum |
   |---------|-------|---------------------|
   | Lambda | Concurrent executions | 100 |
   | Textract | Concurrent requests | 20 |
   | S3 | Buckets | 5 available |
   | DynamoDB | Tables | 2 available |
   | Step Functions | Concurrent executions | 50 |

### Development Tools

Install these tools on your local machine:

```bash
# 1. Python 3.13 or later
python3.13 --version

# 2. Node.js 24 or later
node --version

# 3. AWS CLI
aws --version

# 4. AWS SAM CLI
sam --version

# 5. Docker (for building Lambda layers)
docker --version

# 6. Git
git --version
```

**Install SAM CLI** (if not already installed):

```bash
# macOS
brew install aws-sam-cli

# Linux
pip install aws-sam-cli

# Windows
# Download MSI installer from:
# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
```

### Verify AWS Credentials

Ensure your AWS CLI is configured:

```bash
# Check current credentials
aws sts get-caller-identity

# Configure if needed
aws configure
```

---

## Deployment Steps

RAGStack-Lambda uses a deployment script (`publish.py`) that automates the entire deployment process.

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/RAGStack-Lambda.git
cd RAGStack-Lambda
```

### Step 2: Deploy the Stack

Use the `publish.py` script to deploy (all parameters required):

```bash
# Deploy with all required parameters
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>

# Example: Deploy a customer docs project
python publish.py \
  --project-name customer-docs \
  --admin-email admin@example.com \
  --region us-east-1

# Example: Deploy to different region
python publish.py \
  --project-name legal-archive \
  --admin-email admin@example.com \
  --region us-west-2

# Skip UI build (backend only - faster for backend changes)
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region> \
  --skip-ui
```

**All parameters are required:**
- `--project-name`: Identifies this deployment (lowercase alphanumeric + hyphens, 2-32 chars, must start with letter)
- `--admin-email`: Email for Cognito admin user and CloudWatch/budget alerts
- `--region`: AWS region to deploy to
- `--skip-ui`: (Optional) Skip UI build for backend-only changes

### What Happens During Deployment

The `publish.py` script performs these steps:

1. **Validates inputs and prerequisites** - Checks project name format, Python 3.13+, Node.js 24+, AWS CLI, SAM CLI
2. **Copies shared libraries** - Distributes lib/ragstack_common to Lambda functions
3. **Runs SAM build** - Packages Lambda functions
4. **Deploys infrastructure** - Creates CloudFormation stack with ~60 resources
5. **Builds and deploys UI** - CodeBuild compiles React UI and deploys to S3 (unless `--skip-ui`)
6. **Outputs URLs** - Displays CloudFront URL and next steps

**Deployment time**: Approximately 10-15 minutes for first deployment, 5-10 minutes for updates.

### Step 3: Monitor Deployment

The script will show progress as it deploys. You can also monitor in the AWS Console:

```bash
# Watch CloudFormation stack events
aws cloudformation describe-stack-events \
  --stack-name RAGStack-<project-name> \
  --region <region> \
  --max-items 20

# Or use SAM CLI
sam logs --stack-name RAGStack-<project-name> --tail
```

### Step 4: Save Deployment Outputs

Once deployment completes, the script will output important information:

```
✅ Deployment Complete!

Stack Outputs:
  WebUIUrl: https://d1234567890abc.cloudfront.net
  InputBucketName: ragstack-<project-name>-input-123456789012
  OutputBucketName: ragstack-<project-name>-output-123456789012
  VectorBucketName: ragstack-<project-name>-vectors-123456789012
  TrackingTableName: RAGStack-<project-name>-Tracking
  ApiUrl: https://abcdef123456.appsync-api.us-east-1.amazonaws.com/graphql
  UserPoolId: us-east-1_ABC123DEF

Next Steps:
  1. Check your email (admin@example.com) for temporary password
  2. Open WebUI: https://d1234567890abc.cloudfront.net
  3. Sign in and change your password
  4. Complete post-deployment setup (see DEPLOYMENT.md)
```

**Save these values** - you'll need them for configuration and troubleshooting.

---

## Post-Deployment Configuration

After the stack deploys, you need to manually create the Bedrock Knowledge Base (per ADR-002).

### Manual Knowledge Base Setup

RAGStack-Lambda uses manual KB setup for simplicity. Follow these steps:

#### 1. Create Knowledge Base

1. Go to **AWS Console → Bedrock → Knowledge bases**
2. Click **Create knowledge base**
3. Configure:
   - **Name**: `RAGStack-KB` (or your preferred name)
   - **Description**: "RAGStack document vectors"
   - **IAM role**: Create new service role (default)

#### 2. Configure Data Source

4. Under **Data source**, select **Amazon S3**
5. **S3 URI**: Enter the VectorBucketName from deployment outputs
   - Example: `s3://ragstack-vectors-123456789012/`
6. **Chunking strategy**:
   - **Strategy**: Fixed-size chunking
   - **Max tokens**: 300
   - **Overlap percentage**: 15%
7. Click **Next**

#### 3. Configure Embeddings

8. **Embeddings model**: `amazon.titan-embed-text-v2:0`
9. **Vector database**: Amazon Bedrock (managed)
10. Click **Next** → **Create knowledge base**

#### 4. Get Knowledge Base ID

11. Once created, copy the **Knowledge Base ID** (format: `ABC123DEF`)
12. Also copy the **Data Source ID** from the data source details

#### 5. Store IDs in Parameter Store

Store the IDs so Lambda functions can use them:

```bash
# Replace with your values
KB_ID="ABC123DEF"
DATA_SOURCE_ID="XYZ789GHI"
REGION="<region>"
PROJECT_NAME="<project-name>"
STACK_NAME="RAGStack-${PROJECT_NAME}"

# Store Knowledge Base ID
aws ssm put-parameter \
  --name "/ragstack/${STACK_NAME}/knowledge-base-id" \
  --value "$KB_ID" \
  --type String \
  --region $REGION

# Store Data Source ID
aws ssm put-parameter \
  --name "/ragstack/${STACK_NAME}/data-source-id" \
  --value "$DATA_SOURCE_ID" \
  --type String \
  --region $REGION
```

#### 6. Update Lambda Environment Variables

Update the QueryKB Lambda function with the KB ID:

```bash
aws lambda update-function-configuration \
  --function-name ${STACK_NAME}-QueryKB \
  --environment "Variables={KNOWLEDGE_BASE_ID=$KB_ID,LOG_LEVEL=INFO}" \
  --region $REGION
```

#### 7. Verify Configuration

Test that the KB is accessible:

```bash
aws bedrock-agent list-knowledge-bases --region $REGION
```

You should see your newly created Knowledge Base in the list.

---

## First Login

After deployment, you'll receive an email with a temporary password.

### Step 1: Check Email

Check the inbox for the email address you specified in `--admin-email`:

```
Subject: Your temporary password for RAGStack-Lambda

Username: admin@example.com
Temporary Password: Abc123!TempPass
```

### Step 2: Access WebUI

1. Open the **WebUIUrl** from deployment outputs
2. Sign in with:
   - **Username**: Your email address
   - **Password**: Temporary password from email

### Step 3: Set Permanent Password

1. You'll be prompted to create a new password
2. Password requirements:
   - Minimum 8 characters
   - At least one uppercase letter
   - At least one lowercase letter
   - At least one number
   - At least one special character

### Step 4: Verify Access

After logging in, you should see:
- **Upload** page - Upload documents
- **Dashboard** page - View document processing status
- **Search** page - Query the Knowledge Base

---

## Updating an Existing Deployment

To update an existing deployment with code changes or configuration updates:

### Update Backend Code

```bash
# Make your code changes, then redeploy
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region> \
  --skip-ui
```

### Update UI

```bash
# Make UI changes in src/ui/, then redeploy
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>

# Or deploy UI manually
cd src/ui
npm run build
aws s3 sync build/ s3://ragstack-<project-name>-ui-<account-id>/ --delete
aws cloudfront create-invalidation \
  --distribution-id <distribution-id> \
  --paths "/*"
```

### Update Configuration

To change parameters like OCR backend or model IDs:

```bash
# Edit template.yaml parameters
nano template.yaml

# Then redeploy
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>
```

See [Configuration Guide](CONFIGURATION.md) for details on available parameters.

### Monitor Updates

```bash
# Watch stack update progress
aws cloudformation describe-stacks \
  --stack-name RAGStack-<project-name> \
  --query 'Stacks[0].StackStatus'

# View events
aws cloudformation describe-stack-events \
  --stack-name RAGStack-<project-name> \
  --max-items 10
```

---

## Uninstalling

To completely remove RAGStack-Lambda from your AWS account:

### Step 1: Empty S3 Buckets

CloudFormation cannot delete non-empty buckets. Replace `<project-name>` and `<account-id>` with your values:

```bash
# Get your account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Set your project name
PROJECT_NAME="<project-name>"

# Empty all buckets
aws s3 rm s3://ragstack-${PROJECT_NAME}-input-${ACCOUNT_ID}/ --recursive
aws s3 rm s3://ragstack-${PROJECT_NAME}-output-${ACCOUNT_ID}/ --recursive
aws s3 rm s3://ragstack-${PROJECT_NAME}-vectors-${ACCOUNT_ID}/ --recursive
aws s3 rm s3://ragstack-${PROJECT_NAME}-working-${ACCOUNT_ID}/ --recursive
aws s3 rm s3://ragstack-${PROJECT_NAME}-ui-${ACCOUNT_ID}/ --recursive
aws s3 rm s3://ragstack-${PROJECT_NAME}-cloudtrail-${ACCOUNT_ID}/ --recursive
```

### Step 2: Delete Knowledge Base

The manually created KB must be deleted manually:

```bash
# Delete data source first
aws bedrock-agent delete-data-source \
  --knowledge-base-id <kb-id> \
  --data-source-id <data-source-id>

# Delete knowledge base
aws bedrock-agent delete-knowledge-base \
  --knowledge-base-id <kb-id>
```

### Step 3: Delete CloudFormation Stack

```bash
aws cloudformation delete-stack --stack-name RAGStack-${PROJECT_NAME}

# Monitor deletion
aws cloudformation wait stack-delete-complete --stack-name RAGStack-${PROJECT_NAME}
```

### Step 4: Delete Parameter Store Values

```bash
aws ssm delete-parameter --name "/ragstack/RAGStack-${PROJECT_NAME}/knowledge-base-id"
aws ssm delete-parameter --name "/ragstack/RAGStack-${PROJECT_NAME}/data-source-id"
```

### Step 5: Verify Cleanup

```bash
# Check stack is gone
aws cloudformation describe-stacks --stack-name RAGStack-${PROJECT_NAME}
# Should return: "Stack with id RAGStack-<project-name> does not exist"

# Check S3 buckets are gone
aws s3 ls | grep ragstack-${PROJECT_NAME}
# Should return nothing
```

---

## Cost Estimates

For typical usage (~1000 documents/month, 5 pages each):

| Service | Monthly Cost |
|---------|-------------|
| Textract | $5-15 |
| Bedrock Embeddings | $0.10-0.30 |
| S3 | $0.23 |
| Lambda | $0.20 |
| DynamoDB | $1.25 |
| CloudFront | $0.10 |
| **Total** | **~$7-17/month** |

Using Bedrock OCR instead of Textract adds ~$20-60/month.

See [AWS Pricing Calculator](https://calculator.aws/) for detailed estimates.

---

## Next Steps

After successful deployment:

1. **Read the [User Guide](USER_GUIDE.md)** - Learn how to use the WebUI
2. **Review [Configuration](CONFIGURATION.md)** - Customize your deployment
3. **Test the system** - Follow the [Testing Guide](TESTING.md)
4. **Troubleshooting** - See [Troubleshooting Guide](TROUBLESHOOTING.md) if issues arise

---

## Support

For deployment issues:

- Check [Troubleshooting Guide](TROUBLESHOOTING.md)
- Review CloudWatch logs: `/aws/lambda/RAGStack-*`
- Check CloudFormation events in AWS Console
- Open a GitHub issue with deployment logs
