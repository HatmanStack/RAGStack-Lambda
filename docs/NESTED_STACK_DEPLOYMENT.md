# Nested Stack Deployment

Guide for deploying RAGStack as a nested CloudFormation stack.

## Problem

CloudFormation generates nested stack names with uppercase random suffixes (e.g., `parent-ragstack-84XG2HNPDDZG`). When RAGStack uses this as a bucket name prefix, S3 creation fails because bucket names must be lowercase.

## Solution

Use the `StackPrefix` parameter to provide a lowercase prefix for resource names.

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
      TemplateURL: https://ragstack-quicklaunch-public-631094035453.s3.us-east-1.amazonaws.com/ragstack-template.yaml
      Parameters:
        # Required: Lowercase prefix for bucket names
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

1. **Must be lowercase** - S3 bucket names requirement
2. **Must be unique per AWS account** - Prevents bucket name collisions
3. **Keep it short** - Final bucket names are `{prefix}-{type}-{accountid}` (63 char max)
4. **Valid characters** - Lowercase letters, numbers, hyphens only

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

### Generated Bucket Names

With `StackPrefix: 'my-app-ragstack'` and account ID `123456789012`:

- Data bucket: `my-app-ragstack-data-123456789012`
- Vector bucket: `my-app-ragstack-vectors-123456789012`
- UI bucket: `my-app-ragstack-ui-123456789012`
- Web component bucket: `my-app-ragstack-wc-assets-123456789012`

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

For standalone deployments, **leave StackPrefix empty**. RAGStack will use the stack name:

```bash
# Deploy directly (not nested)
aws cloudformation deploy \
  --template-file ragstack-template.yaml \
  --stack-name my-docs \
  --parameter-overrides AdminEmail=admin@example.com \
  --capabilities CAPABILITY_IAM

# Stack name must be lowercase
# Bucket names: my-docs-data-123456789012, my-docs-vectors-123456789012, etc.
```

## Important Warnings

### ⚠️ NEVER Change StackPrefix After Deployment

Changing `StackPrefix` after initial deployment will:
1. Create **new** buckets with new names
2. **Orphan** existing buckets with all data
3. Require manual data migration

The buckets have `UpdateReplacePolicy: Retain` to prevent data loss, but you'll need to manually copy data from old buckets to new ones.

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
