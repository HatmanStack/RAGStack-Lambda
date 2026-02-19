# Nested Stack Deployment

Guide for deploying RAGStack as a nested CloudFormation stack.

## Problem

CloudFormation generates nested stack names with uppercase random suffixes (e.g., `parent-ragstack-84XG2HNPDDZG`). RAGStack uses stack name as prefix for **all** resource names:
- S3 bucket names (lowercase requirement)
- S3 Vectors index names (lowercase requirement)
- Lambda function names
- DynamoDB table names
- Step Functions state machines
- Log groups
- SSM parameters
- All other AWS resources

Without the `StackPrefix` parameter, deployment fails with errors like:
- `Bucket name should not contain uppercase characters`
- `Invalid index name` (from S3 Vectors CreateIndex operation)

## Solution

Use the `StackPrefix` parameter to provide a lowercase prefix for **all** resource names.

## Parent Stack Template Example

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: Parent stack that deploys RAGStack as a nested stack

Parameters:
  AdminEmail:
    Type: String
    Description: Admin email for RAGStack deployment
    AllowedPattern: '^[\w.+-]+@([\w-]+\.)+[\w-]{2,6}$'

Resources:
  RAGStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://ragstack-quicklaunch-public.s3.us-east-1.amazonaws.com/ragstack-template.yaml
      Parameters:
        # Required: Lowercase prefix for all resource names
        StackPrefix: !Sub '${AWS::StackName}-ragstack'

        # Required: Admin email
        AdminEmail: !Ref AdminEmail

        # Optional: Other parameters
        BuildDashboard: 'true'
        BuildWebComponent: 'true'

      TimeoutInMinutes: 60

Outputs:
  RAGStackGraphQLUrl:
    Description: RAGStack GraphQL API URL
    Value: !GetAtt RAGStack.Outputs.GraphQLApiUrl

  RAGStackUIUrl:
    Description: RAGStack Dashboard URL
    Value: !GetAtt RAGStack.Outputs.UIUrl
```

## Key Points

### StackPrefix Requirements

1. **Must be lowercase** - S3 bucket names and S3 Vectors index names require lowercase
2. **Must be unique per AWS account** - Prevents resource name collisions (especially S3 buckets)
3. **Keep it short** - S3 bucket names have 63 char max: `{prefix}-{type}-{accountid}`
4. **Valid characters** - Lowercase letters, numbers, hyphens only
5. **Applies to all resources** - Lambda functions, DynamoDB tables, Step Functions, log groups, etc.

### Example Prefix Patterns

```yaml
# Good: Lowercase, unique
StackPrefix: 'my-app-ragstack'
StackPrefix: !Sub '${AWS::StackName}-docs'  # If parent stack name is lowercase
StackPrefix: 'prod-knowledge-base'

# Bad: Has uppercase
StackPrefix: 'MyApp-RAGStack'  # ❌ Will fail

# Bad: Generic (might collide)
StackPrefix: 'ragstack'  # ❌ Not unique enough
```

### Generated Resource Names

With `StackPrefix: 'my-app-ragstack'` and account ID `123456789012`:

**S3 Buckets:**
- Data bucket: `my-app-ragstack-data-123456789012`
- Vector bucket: `my-app-ragstack-vectors-123456789012`
- UI bucket: `my-app-ragstack-ui-123456789012`
- Web component bucket: `my-app-ragstack-wc-assets-123456789012`

**Other Resources:**
- Lambda functions: `my-app-ragstack-process`, `my-app-ragstack-ingest`, etc.
- DynamoDB tables: `my-app-ragstack-tracking`, `my-app-ragstack-config`, etc.
- Knowledge Base index: `my-app-ragstack-index`
- Step Functions: `my-app-ragstack-ProcessingPipeline`, `my-app-ragstack-ScrapeWorkflow`
- Log groups: `/aws/vendedlogs/states/my-app-ragstack-Pipeline`

## Deployment Commands

```bash
# Deploy parent stack
aws cloudformation deploy \
  --template-file parent-stack.yaml \
  --stack-name my-parent-stack \
  --parameter-overrides AdminEmail=admin@example.com \
  --capabilities CAPABILITY_IAM

# Check status
aws cloudformation describe-stacks \
  --stack-name my-parent-stack \
  --query 'Stacks[0].StackStatus'

# Get outputs
aws cloudformation describe-stacks \
  --stack-name my-parent-stack \
  --query 'Stacks[0].Outputs'
```

## Standalone Deployment (No StackPrefix)

For standalone deployments, **leave StackPrefix empty**. RAGStack will use the stack name as prefix for all resources:

```bash
# Deploy directly (not nested)
aws cloudformation deploy \
  --template-file ragstack-template.yaml \
  --stack-name my-docs \
  --parameter-overrides AdminEmail=admin@example.com \
  --capabilities CAPABILITY_IAM

# Stack name must be lowercase
# All resources prefixed with stack name:
# - Buckets: my-docs-data-123456789012, my-docs-vectors-123456789012
# - Lambda: my-docs-process, my-docs-ingest
# - Tables: my-docs-tracking, my-docs-config
```

## Important Warnings

### ⚠️ NEVER Change StackPrefix After Deployment

Changing `StackPrefix` after initial deployment will:
1. Create **new** resources with new names (S3 buckets, DynamoDB tables, Lambda functions, etc.)
2. **Orphan** existing resources with all data
3. Require manual data migration and configuration updates

S3 buckets and DynamoDB tables have `UpdateReplacePolicy: Retain` to prevent data loss, but you'll need to:
- Manually copy data from old buckets to new ones
- Migrate DynamoDB table data
- Update any external references to Lambda functions, API endpoints, etc.

### ⚠️ Stack Name Requirements

If using stack name as prefix (no StackPrefix parameter):
- **Must be lowercase** - CloudFormation allows uppercase but S3 buckets don't
- Example valid: `my-docs`, `prod-kb`, `staging-ragstack`
- Example invalid: `MyDocs`, `Prod-KB`, `RAGSTACK`

## Troubleshooting

### Error: "Bucket name should not contain uppercase characters"

**Cause**: StackPrefix contains uppercase letters or stack name is uppercase (for standalone deployments)

**Solution**:
```yaml
# For nested deployment - fix StackPrefix
Parameters:
  StackPrefix: 'my-app-ragstack'  # All lowercase

# For standalone deployment - use lowercase stack name
aws cloudformation deploy --stack-name my-docs  # Not My-Docs
```

### Error: "Bucket already exists"

**Cause**: StackPrefix is not unique in your AWS account

**Solution**: Use a more specific prefix
```yaml
# Add environment, app name, or timestamp
StackPrefix: 'prod-myapp-ragstack'
StackPrefix: !Sub '${Environment}-${ApplicationName}-ragstack'
```

### Error: "Bucket name too long"

**Cause**: StackPrefix + suffix exceeds 63 characters

**Solution**: Shorten the prefix
```yaml
# Too long (>63 chars)
StackPrefix: 'my-very-long-application-name-production-ragstack'

# Fixed
StackPrefix: 'myapp-prod-ragstack'
```

## Migration from Standalone to Nested

You cannot directly migrate an existing standalone deployment to nested deployment. Options:

1. **Deploy new nested stack** with different StackPrefix, migrate data manually
2. **Keep as standalone** - No migration needed, works fine

## See Also

- [Main README](../README.md) - General deployment instructions
- [Configuration Guide](./CONFIGURATION.md) - Runtime configuration options
- [Architecture](./ARCHITECTURE.md) - System design
