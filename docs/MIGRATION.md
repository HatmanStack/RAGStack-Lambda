# Migration Guide: Environment-Based to Project-Based Deployment

## Overview

This guide helps you migrate from the old environment-based deployment system (`--env dev/prod`) to the new project-based system.

## What Changed

### Old System (Before)
```bash
./publish.sh --env dev --admin-email admin@example.com
./publish.sh --env prod --admin-email admin@example.com
```

- Configurations stored in `samconfig.toml`
- Limited to predefined environments (dev/prod)
- Used `publish.sh` wrapper script
- Stack names: `RAGStack-dev`, `RAGStack-prod`

### New System (After)
```bash
python publish.py \
  --project-name customer-docs \
  --admin-email admin@example.com \
  --region us-east-1
```

- All parameters required on CLI (no stored configs)
- Unlimited project names (any valid identifier)
- Run `publish.py` directly (no wrapper)
- Stack names: `RAGStack-<project-name>`

## Migration Steps

### Step 1: Note Your Current Deployments

List existing stacks:
```bash
aws cloudformation list-stacks \
  --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query 'StackSummaries[?contains(StackName, `RAGStack`)].StackName' \
  --output table
```

Document for each stack:
- Stack name
- Region
- Admin email (from parameters)
- Purpose/environment

### Step 2: Deploy New Project-Based Stacks

Deploy new stacks with project names:

```bash
# Replace old "dev" environment
python publish.py \
  --project-name myapp-dev \
  --admin-email dev-admin@example.com \
  --region us-east-1

# Replace old "prod" environment
python publish.py \
  --project-name myapp-prod \
  --admin-email prod-admin@example.com \
  --region us-east-1
```

**Note**: New stack names will be different, so this creates new resources.

### Step 3: Migrate Data (If Needed)

If you need to preserve data from old deployments:

**DynamoDB Tables:**
```bash
# Export from old table
aws dynamodb scan --table-name RAGStack-dev-Tracking > old-tracking.json

# Import to new table
aws dynamodb batch-write-item --request-items file://import-tracking.json
```

**S3 Documents:**
```bash
# Copy documents between buckets
aws s3 sync \
  s3://ragstack-input-123456789012/ \
  s3://ragstack-myapp-dev-input-123456789012/
```

**Knowledge Base:**
- Note: KB must be manually recreated (as before)
- Follow post-deployment setup in DEPLOYMENT.md

### Step 4: Update CI/CD Pipelines

Update deployment scripts in CI/CD:

**Before:**
```bash
./publish.sh --env $ENVIRONMENT --admin-email $ADMIN_EMAIL
```

**After:**
```bash
python publish.py \
  --project-name $PROJECT_NAME \
  --admin-email $ADMIN_EMAIL \
  --region $AWS_REGION
```

**Environment variables to update:**
- Remove: `ENVIRONMENT` variable
- Add: `PROJECT_NAME` variable
- Add: `AWS_REGION` variable (was implicit before)

### Step 5: Delete Old Stacks

After verifying new deployments work:

1. Empty S3 buckets from old stacks
2. Delete old stacks:
```bash
aws cloudformation delete-stack --stack-name RAGStack-dev
aws cloudformation delete-stack --stack-name RAGStack-prod
```

## Key Differences

### Resource Naming

**Old:**
- Stack: `RAGStack-dev`
- Bucket: `ragstack-dev-input-123456789012`
- Lambda: `RAGStack-dev-ProcessDocument`

**New:**
- Stack: `RAGStack-customer-docs`
- Bucket: `ragstack-customer-docs-input-123456789012`
- Lambda: `RAGStack-customer-docs-ProcessDocument`

### Configuration

**Old:**
- Stored in `samconfig.toml` under `[dev]` or `[prod]`
- Could omit parameters on CLI

**New:**
- No stored configuration (minimal `samconfig.toml`)
- All parameters required on CLI every time

### Deployment Script

**Old:**
```bash
./publish.sh --env dev
```

**New:**
```bash
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>
```

## Benefits of New System

1. **Unlimited Deployments**: Deploy as many independent projects as needed
2. **Explicit Configuration**: No hidden defaults or stored state
3. **Clear Identity**: Project name clearly identifies each deployment
4. **No Conflicts**: Multiple team members can deploy different projects
5. **Simpler Codebase**: One script (`publish.py`) instead of two

## Troubleshooting

**Issue**: "Command not found: ./publish.sh"

**Solution**: Use `python publish.py` instead - the wrapper script was removed

**Issue**: "Missing required argument: --project-name"

**Solution**: All three parameters are now required:
```bash
python publish.py \
  --project-name <project-name> \
  --admin-email <email> \
  --region <region>
```

**Issue**: Old stack still exists alongside new stack

**Solution**: This is expected - new project-based stacks use different names. Delete old stacks after migrating data.

## Support

For questions or issues during migration:
- Review Phase-0.md ADRs in `docs/plans/` for architectural decisions
- Check `docs/DEPLOYMENT.md` for deployment procedures
- Open GitHub issue with migration questions
