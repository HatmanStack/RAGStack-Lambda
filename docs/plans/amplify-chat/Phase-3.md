# Phase 3: Amplify Infrastructure & CDN Deployment

**Goal:** Add CDN infrastructure to Amplify backend and integrate web component deployment into publish.py.

**Dependencies:** Phase 0 (ADRs), Phase 1 (packaging function), Phase 2 (web component source)

**Deliverables:**
- CDN resources in `amplify/backend.ts` (S3, CloudFront, CodeBuild)
- Enhanced `write_amplify_config()` to include ConfigurationTable name and source location
- Enhanced `amplify_deploy()` to trigger CodeBuild
- New `get_amplify_stack_outputs()` function
- Integration with deployment flow

**Estimated Scope:** ~30,000 tokens

---

## Context

This phase creates the CDN infrastructure that hosts the web component and integrates it into the deployment flow:

1. **Amplify Backend** - Add CDK resources to `backend.ts` (CloudFront, S3, CodeBuild)
2. **publish.py Integration** - Call packaging function, update config generation, trigger build
3. **Output Display** - Show CDN URL after deployment

After this phase, `publish.py --deploy-chat` will deploy a working (but basic) chat component to CDN.

---

## Task 1: Add CDN Resources to Amplify Backend

### Goal

Extend `amplify/backend.ts` to create S3 bucket, CloudFront distribution, and CodeBuild project for web component deployment.

### Files to Modify

- `amplify/backend.ts`

### Background

Currently `amplify/backend.ts` only has:
```typescript
export const backend = defineBackend({ auth, data });
```

We'll add a new stack with CDN resources, following Amplify Gen 2 patterns for custom resources.

### Instructions

1. **Add imports at top of file:**

   ```typescript
   import { defineBackend } from '@aws-amplify/backend';
   import { Stack, CfnOutput, Duration, RemovalPolicy } from 'aws-cdk-lib';
   import { Bucket, BlockPublicAccess } from 'aws-cdk-lib/aws-s3';
   import {
     Distribution,
     ViewerProtocolPolicy,
     CachePolicy,
     OriginAccessIdentity,
   } from 'aws-cdk-lib/aws-cloudfront';
   import { S3Origin } from 'aws-cdk-lib/aws-cloudfront-origins';
   import {
     Project,
     BuildSpec,
     LinuxBuildImage,
     ComputeType,
   } from 'aws-cdk-lib/aws-codebuild';
   import { PolicyStatement, Effect } from 'aws-cdk-lib/aws-iam';
   import { auth } from './auth/resource';
   import { data } from './data/resource';
   ```

2. **After the `defineBackend()` call, add CDN stack:**

   ```typescript
   export const backend = defineBackend({
     auth,
     data,
   });

   // Create custom stack for web component CDN
   const cdnStack = backend.createStack('web-component-cdn');

   // S3 bucket for web component assets
   const assetBucket = new Bucket(cdnStack, 'WebComponentAssets', {
     blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
     versioned: true,
     removalPolicy: RemovalPolicy.RETAIN, // Retain bucket on stack deletion
   });

   // Origin Access Identity for CloudFront -> S3
   const oai = new OriginAccessIdentity(cdnStack, 'OAI', {
     comment: 'OAI for web component distribution',
   });

   assetBucket.grantRead(oai);

   // CloudFront distribution
   const distribution = new Distribution(cdnStack, 'WebComponentCDN', {
     defaultBehavior: {
       origin: new S3Origin(assetBucket, { originAccessIdentity: oai }),
       viewerProtocolPolicy: ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
       cachePolicy: CachePolicy.CACHING_OPTIMIZED,
       compress: true,
     },
     defaultRootObject: 'amplify-chat.js',
     comment: 'CDN for Amplify Chat web component',
   });

   // CodeBuild project to build and deploy web component
   const buildProject = new Project(cdnStack, 'WebComponentBuild', {
     projectName: `${cdnStack.stackName}-web-component-build`,
     description: 'Build and deploy Amplify Chat web component to CDN',
     buildSpec: BuildSpec.fromObject({
       version: '0.2',
       phases: {
         install: {
           'runtime-versions': {
             nodejs: '24',
           },
           commands: [
             'echo "Installing dependencies..."',
             'cd web-component',
             'npm ci',
           ],
         },
         build: {
           commands: [
             'echo "Building web component..."',
             'npm run build',
             'ls -lh dist/',
           ],
         },
         post_build: {
           commands: [
             'echo "Deploying to S3..."',
             'aws s3 cp dist/wc.js s3://${ASSET_BUCKET}/amplify-chat.js --content-type application/javascript --cache-control "public, max-age=31536000"',
             'aws s3 cp dist/wc.esm.js s3://${ASSET_BUCKET}/amplify-chat.esm.js --content-type application/javascript --cache-control "public, max-age=31536000"',
             'echo "Invalidating CloudFront cache..."',
             'aws cloudfront create-invalidation --distribution-id ${DISTRIBUTION_ID} --paths "/amplify-chat.js" "/amplify-chat.esm.js"',
             'echo "Deployment complete!"',
           ],
         },
       },
     }),
     environment: {
       buildImage: LinuxBuildImage.STANDARD_7_0,
       computeType: ComputeType.SMALL,
       environmentVariables: {
         ASSET_BUCKET: { value: assetBucket.bucketName },
         DISTRIBUTION_ID: { value: distribution.distributionId },
       },
     },
     timeout: Duration.minutes(15),
   });

   // Grant CodeBuild permissions
   assetBucket.grantReadWrite(buildProject);
   buildProject.addToRolePolicy(
     new PolicyStatement({
       effect: Effect.ALLOW,
       actions: ['cloudfront:CreateInvalidation'],
       resources: [
         `arn:aws:cloudfront::${cdnStack.account}:distribution/${distribution.distributionId}`,
       ],
     })
   );

   // Grant access to source bucket (artifacts uploaded by publish.py)
   // Use specific bucket from config to avoid cross-project access
   buildProject.addToRolePolicy(
     new PolicyStatement({
       effect: Effect.ALLOW,
       actions: ['s3:GetObject', 's3:ListBucket'],
       resources: [
         `arn:aws:s3:::${KNOWLEDGE_BASE_CONFIG.webComponentSourceBucket}`,
         `arn:aws:s3:::${KNOWLEDGE_BASE_CONFIG.webComponentSourceBucket}/*`,
       ],
     })
   );

   // Stack outputs for publish.py
   new CfnOutput(cdnStack, 'WebComponentCDN', {
     value: `https://${distribution.distributionDomainName}/amplify-chat.js`,
     description: 'CDN URL for embeddable chat web component',
     exportName: `${cdnStack.stackName}-WebComponentCDN`,
   });

   new CfnOutput(cdnStack, 'AssetBucketName', {
     value: assetBucket.bucketName,
     description: 'S3 bucket for web component assets',
     exportName: `${cdnStack.stackName}-AssetBucketName`,
   });

   new CfnOutput(cdnStack, 'BuildProjectName', {
     value: buildProject.projectName,
     description: 'CodeBuild project name for web component deployment',
     exportName: `${cdnStack.stackName}-BuildProjectName`,
   });

   new CfnOutput(cdnStack, 'DistributionId', {
     value: distribution.distributionId,
     description: 'CloudFront distribution ID',
     exportName: `${cdnStack.stackName}-DistributionId`,
   });
   ```

3. **Verify TypeScript compiles:**

   ```bash
   cd amplify
   npx tsc --noEmit
   ```

### Verification Checklist

- [ ] Imports added for CDK constructs
- [ ] S3 bucket created with versioning enabled
- [ ] CloudFront distribution with HTTPS redirect
- [ ] CodeBuild project with Node 24 runtime
- [ ] BuildSpec downloads source, builds, uploads to S3, invalidates CloudFront
- [ ] IAM permissions granted (S3 read/write, CloudFront invalidation, source bucket access)
- [ ] Four CfnOutputs defined
- [ ] No TypeScript errors

### Testing

Deploy Amplify stack to verify resources are created (requires existing SAM deployment):

```bash
# From project root, ensure you're in deploy-amplify worktree
cd /root/RAGStack-Lambda/.worktrees/deploy-amplify

# Create mock config (Phase 1 would normally set this)
mkdir -p amplify/data
cat > amplify/data/config.ts <<EOF
export const KNOWLEDGE_BASE_CONFIG = {
  knowledgeBaseId: 'MOCK123',
  region: 'us-east-1',
  configurationTableName: 'MockTable',
  webComponentSourceBucket: 'mock-bucket',
  webComponentSourceKey: 'mock-key.zip',
} as const;
EOF

# Deploy Amplify (may take 10-15 minutes)
npx ampx deploy --yes

# Verify outputs
npx ampx outputs

# Should see:
# - WebComponentCDN: https://d1234567890.cloudfront.net/amplify-chat.js
# - AssetBucketName: amplify-stack-name-webcomponentassets-xyz
# - BuildProjectName: amplify-stack-name-web-component-build
# - DistributionId: E1234567890ABC
```

### Commit

```bash
git add amplify/backend.ts
git commit -m "feat(amplify): add CDN infrastructure for web component

- Create S3 bucket for web component assets
- Add CloudFront distribution with HTTPS redirect
- Create CodeBuild project with Node 24 build environment
- Grant IAM permissions for S3, CloudFront, source bucket access
- Output CDN URL and resource names for publish.py integration"
```

---

## Task 2: Update Amplify Config Generation

### Goal

Modify `write_amplify_config()` in publish.py to include ConfigurationTable name and web component source location.

### Files to Modify

- `publish.py` (function: `write_amplify_config()`, around line 765)

### Background

Currently `write_amplify_config()` writes:
```typescript
export const KNOWLEDGE_BASE_CONFIG = {
  knowledgeBaseId: "...",
  region: "...",
}
```

We need to add:
- `configurationTableName` (for Phase 4's config reading)
- `webComponentSourceBucket` (for CodeBuild source download)
- `webComponentSourceKey` (for CodeBuild source download)

### Instructions

1. **Modify function signature:**

   Change:
   ```python
   def write_amplify_config(kb_id, region):
   ```

   To:
   ```python
   def write_amplify_config(kb_id, region, config_table_name, source_bucket, source_key):
   ```

2. **Update config content generation:**

   Change the `config_content` string to:

   ```python
   config_content = f'''/**
    * Amplify Chat Backend Configuration
    *
    * This file is auto-generated by publish.py during deployment.
    * It contains the Knowledge Base ID from the SAM stack and AWS region configuration.
    *
    * DO NOT edit manually - changes will be overwritten on next deployment.
    */

   export const KNOWLEDGE_BASE_CONFIG = {{
     // Bedrock Knowledge Base ID from SAM deployment
     // Retrieved from CloudFormation stack outputs
     knowledgeBaseId: "{kb_id}",

     // AWS Region where Bedrock Knowledge Base is deployed
     region: "{region}",

     // ConfigurationTable name for runtime config reading
     // Amplify Lambda reads chat settings from this table
     configurationTableName: "{config_table_name}",

     // Web component source location (for CodeBuild)
     // CodeBuild downloads and extracts this zip to build the component
     webComponentSourceBucket: "{source_bucket}",
     webComponentSourceKey: "{source_key}",
   }} as const;

   // Type-safe export for use in resource.ts
   export type KnowledgeBaseConfig = typeof KNOWLEDGE_BASE_CONFIG;
   '''
   ```

3. **Update docstring:**

   ```python
   """
   Generate TypeScript config file for Amplify backend.

   Creates amplify/data/config.ts with Knowledge Base ID, region,
   ConfigurationTable name, and web component source location.

   This config is imported by data/resource.ts and used by:
   - Conversation route (queries KB, reads config)
   - CodeBuild (downloads source from S3)

   Args:
       kb_id: Bedrock Knowledge Base ID
       region: AWS region
       config_table_name: DynamoDB ConfigurationTable name
       source_bucket: S3 bucket containing web component source
       source_key: S3 key of web component source zip

   Raises:
       IOError: If config file creation fails
   """
   ```

4. **Find all call sites and update:**

   Search for `write_amplify_config(` in publish.py. Update each call to pass new parameters.

   You'll find calls in the `--chat-only` path and `--deploy-chat` path in `main()`.

   For now, pass placeholder values. We'll fix the actual values in Task 3.

   Example:
   ```python
   write_amplify_config(
       kb_id,
       args.region,
       'PLACEHOLDER_TABLE',  # Will be fixed in Task 3
       'PLACEHOLDER_BUCKET',  # Will be fixed in Task 3
       'PLACEHOLDER_KEY'  # Will be fixed in Task 3
   )
   ```

### Verification Checklist

- [ ] Function signature includes 5 parameters
- [ ] Config content includes all 5 fields
- [ ] Docstring updated
- [ ] All call sites updated (may use placeholders for now)
- [ ] No syntax errors: `python -m py_compile publish.py`

### Commit

```bash
git add publish.py
git commit -m "feat(publish): extend write_amplify_config with table name and source location

- Add configurationTableName parameter (for Phase 4 config reading)
- Add webComponentSourceBucket and webComponentSourceKey (for CodeBuild)
- Update function signature and docstring
- Update call sites (placeholders for now, will be fixed in Task 3)"
```

---

## Task 3: Enhance Amplify Deployment Function

### Goal

Update `amplify_deploy()` to package web component source, update config generation with real values, deploy Amplify, and trigger CodeBuild.

### Files to Modify

- `publish.py` (function: `amplify_deploy()`, around line 827)

### Background

Current `amplify_deploy()`:
1. Checks if `amplify/` exists
2. Runs `npx ampx deploy --yes`

We need to:
1. **Before deploy:** Package web component source (call Phase 1's function)
2. **Before deploy:** Update config file with real values
3. **After deploy:** Get stack outputs
4. **After deploy:** Trigger CodeBuild
5. **Return:** CDN URL

### Instructions

1. **Modify function signature:**

   Change:
   ```python
   def amplify_deploy(project_name, region):
   ```

   To:
   ```python
   def amplify_deploy(project_name, region, kb_id, artifact_bucket, config_table_name):
   ```

2. **Replace function body:**

   ```python
   def amplify_deploy(project_name, region, kb_id, artifact_bucket, config_table_name):
       """
       Deploy Amplify chat backend with web component CDN.

       This function:
       1. Packages web component source to S3
       2. Generates amplify/data/config.ts with KB ID, table name, source location
       3. Deploys Amplify stack (GraphQL API, Lambda, Cognito, CDN)
       4. Triggers CodeBuild to build and deploy web component
       5. Returns CDN URL for embedding

       Args:
           project_name: Project name for stack naming
           region: AWS region
           kb_id: Bedrock Knowledge Base ID (from SAM stack)
           artifact_bucket: S3 bucket for web component source
           config_table_name: DynamoDB ConfigurationTable name (from SAM stack)

       Returns:
           str: CDN URL for web component (https://d123.cloudfront.net/amplify-chat.js)

       Raises:
           subprocess.CalledProcessError: If deployment fails
           FileNotFoundError: If amplify/ directory not found
           IOError: If packaging or CodeBuild trigger fails
       """
       log_info("Deploying Amplify chat backend...")

       # Check if amplify directory exists
       amplify_dir = Path('amplify')
       if not amplify_dir.exists():
           raise FileNotFoundError(
               "Amplify project not found at amplify/. "
               "Ensure you're in the correct directory."
           )

       # Step 1: Package web component source
       log_info("Packaging web component source...")
       try:
           chat_source_key = package_amplify_chat_source(artifact_bucket, region)
           log_success(f"Web component source uploaded: s3://{artifact_bucket}/{chat_source_key}")
       except (FileNotFoundError, IOError) as e:
           log_error(f"Failed to package web component: {e}")
           raise

       # Step 2: Generate amplify/data/config.ts with all parameters
       log_info("Generating Amplify backend configuration...")
       try:
           write_amplify_config(
               kb_id,
               region,
               config_table_name,
               artifact_bucket,
               chat_source_key
           )
           write_amplify_env(kb_id, region)  # Also write .env.amplify
           log_success("Amplify configuration generated")
       except Exception as e:
           log_error(f"Failed to generate Amplify configuration: {e}")
           raise IOError(f"Config generation failed: {e}") from e

       # Step 3: Deploy Amplify stack
       log_info("Deploying Amplify stack (GraphQL API, Lambda, Cognito, CDN)...")
       log_info("This may take 10-15 minutes...")
       try:
           run_command(['npx', 'ampx', 'deploy', '--yes'], cwd=str(Path.cwd()))
           log_success("Amplify stack deployed successfully")
       except subprocess.CalledProcessError as e:
           log_error(f"Amplify deployment failed: {e}")
           raise

       # Step 4: Get Amplify stack outputs
       log_info("Retrieving Amplify stack outputs...")
       try:
           outputs = get_amplify_stack_outputs(project_name, region)
           cdn_url = outputs.get('WebComponentCDN')
           build_project = outputs.get('BuildProjectName')

           if not cdn_url or not build_project:
               log_error("Missing required outputs from Amplify stack")
               log_error(f"Outputs: {outputs}")
               raise ValueError("Amplify stack outputs incomplete")

           log_info(f"CDN URL: {cdn_url}")
           log_info(f"Build Project: {build_project}")
       except Exception as e:
           log_error(f"Failed to retrieve Amplify outputs: {e}")
           raise IOError(f"Output retrieval failed: {e}") from e

       # Step 5: Trigger CodeBuild to build and deploy web component
       log_info("Triggering web component build and deployment...")
       build_id = None
       try:
           codebuild = boto3.client('codebuild', region_name=region)

           # Trigger build with source location
           build_response = codebuild.start_build(
               projectName=build_project,
               sourceLocationOverride=f'{artifact_bucket}/{chat_source_key}',
               sourceTypeOverride='S3',
           )

           build_id = build_response['build']['id']
           log_info(f"Build started: {build_id}")
           log_info("Check CloudWatch Logs for build progress:")
           log_info(f"  https://console.aws.amazon.com/codesuite/codebuild/projects/{build_project}/build/{build_id}")

           # Don't wait for build to complete (can take 5-10 minutes)
           # User can monitor in CloudWatch
           log_success("Web component build triggered (running asynchronously)")

       except Exception as e:
           log_error(f"Failed to trigger CodeBuild: {e}")
           log_warning("Amplify stack deployed, but web component build failed")
           log_warning("RECOVERY OPTIONS:")
           log_warning(f"  1. Manually trigger build in CodeBuild console: {build_project}")
           log_warning(f"  2. Run: aws codebuild start-build --project-name {build_project}")
           log_warning(f"  3. Redeploy with --chat-only flag to retry")
           # Don't raise - stack is deployed successfully, just build failed

       # Step 6: Return CDN URL (even if build failed - it can be triggered manually)
       log_success(f"Amplify deployment complete! CDN URL: {cdn_url}")
       log_warning("Note: Web component may not be available at CDN URL until CodeBuild completes")
       return cdn_url
   ```

3. **Update docstring for `write_amplify_env()`:**

   Find `write_amplify_env()` (around line 807) and verify it exists. No changes needed to function body.

### Verification Checklist

- [ ] Function signature updated with 5 parameters
- [ ] Calls `package_amplify_chat_source()` from Phase 1
- [ ] Calls `write_amplify_config()` with real values
- [ ] Deploys Amplify with `npx ampx deploy`
- [ ] Calls `get_amplify_stack_outputs()` (will create in Task 4)
- [ ] Triggers CodeBuild with `start_build()`
- [ ] Returns CDN URL string
- [ ] Error handling for each step

### Commit

**Wait until Task 4 (get_amplify_stack_outputs created) before committing.**

---

## Task 4: Create Amplify Stack Outputs Function

### Goal

Create `get_amplify_stack_outputs()` function to retrieve CloudFormation outputs from the Amplify-deployed stack.

### Files to Modify

- `publish.py` (add new function after `get_stack_outputs()`)

### Background

SAM stack outputs are retrieved with `get_stack_outputs()` which uses CloudFormation `describe_stacks`.

Amplify Gen 2 creates a stack named `amplify-{appId}-{branchName}-{hash}`. We need to find it and read outputs.

### Instructions

1. **Add function after existing `get_stack_outputs()`:**

   ```python
   def get_amplify_stack_outputs(project_name, region):
       """
       Get CloudFormation stack outputs from Amplify deployment.

       Amplify Gen 2 creates stacks with pattern: amplify-{appId}-{branch}-{hash}
       We search for stacks starting with "amplify-" to find the deployed stack.

       Args:
           project_name: Project name (used for identification)
           region: AWS region

       Returns:
           dict: Stack outputs as key-value pairs
               {
                   'WebComponentCDN': 'https://d123.cloudfront.net/amplify-chat.js',
                   'AssetBucketName': 'amplify-stack-assets-xyz',
                   'BuildProjectName': 'amplify-stack-build',
                   'DistributionId': 'E1234567890ABC'
               }

       Raises:
           ValueError: If Amplify stack not found or has no outputs
       """
       log_info("Fetching Amplify stack outputs...")

       cf_client = boto3.client('cloudformation', region_name=region)

       try:
           # List all stacks (active only)
           paginator = cf_client.get_paginator('list_stacks')
           stack_iterator = paginator.paginate(
               StackStatusFilter=[
                   'CREATE_COMPLETE',
                   'UPDATE_COMPLETE',
                   'UPDATE_ROLLBACK_COMPLETE'
               ]
           )

           # Find Amplify stacks with timestamps (collect from list_stacks)
           amplify_stacks = []
           for page in stack_iterator:
               for stack in page['StackSummaries']:
                   if stack['StackName'].startswith('amplify-'):
                       amplify_stacks.append({
                           'StackName': stack['StackName'],
                           'LastUpdatedTime': stack.get('LastUpdatedTime', stack['CreationTime'])
                       })

           if not amplify_stacks:
               raise ValueError(
                   "No Amplify stacks found. Ensure 'npx ampx deploy' completed successfully."
               )

           # Sort by LastUpdatedTime (already have it from list_stacks)
           amplify_stacks.sort(key=lambda s: s['LastUpdatedTime'], reverse=True)
           stack_name = amplify_stacks[0]['StackName']

           log_info(f"Found Amplify stack: {stack_name}")

           # Get stack outputs
           response = cf_client.describe_stacks(StackName=stack_name)
           outputs = response['Stacks'][0].get('Outputs', [])

           if not outputs:
               raise ValueError(f"Amplify stack '{stack_name}' has no outputs")

           # Convert to dict
           output_dict = {}
           for item in outputs:
               output_dict[item['OutputKey']] = item['OutputValue']

           log_success(f"Retrieved {len(output_dict)} outputs from Amplify stack")
           return output_dict

       except Exception as e:
           log_error(f"Failed to get Amplify stack outputs: {e}")
           raise ValueError(f"Could not retrieve Amplify outputs: {e}") from e
   ```

### Verification Checklist

- [ ] Function searches for stacks starting with "amplify-"
- [ ] Selects most recently updated stack
- [ ] Returns dict of outputs
- [ ] Error handling for "no stacks found" and "no outputs"
- [ ] Uses existing logging helpers

### Commit

Now commit both Task 3 and Task 4 together:

```bash
git add publish.py
git commit -m "feat(publish): enhance amplify_deploy with full deployment flow

- Package web component source before deployment
- Generate config with table name and source location
- Deploy Amplify stack with npx ampx deploy
- Retrieve stack outputs (CDN URL, build project, etc.)
- Trigger CodeBuild asynchronously
- Add get_amplify_stack_outputs to find and read Amplify stack
- Return CDN URL for output display"
```

---

## Task 5: Update Main Deployment Flow

### Goal

Modify `main()` in publish.py to call enhanced `amplify_deploy()` with correct parameters and update `seed_configuration_table()` to set `chat_deployed=True`.

### Files to Modify

- `publish.py` (function: `main()`, around line 961)

### Background

The `--deploy-chat` flow in `main()` currently:
1. Deploys SAM
2. Extracts KB ID
3. Calls `amplify_deploy(project_name, region)` with 2 params

We need to:
1. Extract KB ID and ConfigurationTable name from SAM
2. Call `amplify_deploy()` with 5 params
3. Update `seed_configuration_table()` to set `chat_deployed=True`
4. Display CDN URL in final outputs

### Instructions

1. **Find the `--deploy-chat` section** in `main()` (around line 1162):

   ```python
   if args.deploy_chat:
       log_info("SAM deployment complete. Now deploying Amplify chat backend...")
       # ...existing code...
   ```

2. **Update to extract ConfigurationTable name:**

   Change:
   ```python
   # Extract KB ID from SAM outputs
   try:
       kb_id = extract_knowledge_base_id(stack_name, args.region)
   except ValueError as e:
       log_error(str(e))
       log_warning("Chat deployment skipped due to KB ID not found")
       sys.exit(0)
   ```

   To:
   ```python
   # Extract KB ID and ConfigurationTable name from SAM outputs
   try:
       kb_id = extract_knowledge_base_id(stack_name, args.region)

       # Get ConfigurationTable name from SAM outputs
       sam_outputs = get_stack_outputs(stack_name, args.region)
       config_table_name = sam_outputs.get('ConfigurationTableName')

       if not config_table_name:
           raise ValueError("ConfigurationTableName not found in SAM stack outputs")

       log_info(f"Knowledge Base ID: {kb_id}")
       log_info(f"Configuration Table: {config_table_name}")

   except ValueError as e:
       log_error(str(e))
       log_warning("Chat deployment skipped due to missing SAM outputs")
       sys.exit(0)
   ```

3. **Update amplify_deploy() call:**

   Change:
   ```python
   try:
       amplify_deploy(args.project_name, args.region)
       log_success("Amplify chat backend deployed successfully!")
   except Exception as e:
       log_error(f"Amplify deployment failed: {e}")
       log_warning("SAM core is deployed, but chat backend deployment failed")
       sys.exit(1)
   ```

   To:
   ```python
   try:
       # Set chat_deployed=True BEFORE Amplify deploy to avoid race condition
       # If deploy fails, flag is set but no harm (chat won't work, but UI shows it)
       log_info("Marking chat as deployed in configuration...")
       seed_configuration_table(stack_name, args.region, chat_deployed=True)

       cdn_url = amplify_deploy(
           args.project_name,
           args.region,
           kb_id,
           artifact_bucket,
           config_table_name
       )

       log_success("Amplify chat backend deployed successfully!")
       log_success(f"Chat CDN URL: {cdn_url}")

       # Add CDN URL to outputs for final display
       outputs['ChatCDN'] = cdn_url

   except Exception as e:
       log_error(f"Amplify deployment failed: {e}")
       log_warning("SAM core is deployed, but chat backend deployment failed")
       log_warning("Note: chat_deployed flag was set but deployment failed")
       log_warning("  Admins may see chat settings UI, but functionality won't work")
       log_warning("  To fix: Retry deployment or manually set chat_deployed=false in DynamoDB")
       sys.exit(1)
   ```

4. **Update print_outputs() to display CDN URL:**

   Find `print_outputs()` function (around line 702). Add after the UI URL section:

   ```python
   # Print Chat CDN URL if available
   if 'ChatCDN' in outputs:
       print(f"\n{Colors.OKGREEN}Chat Component:{Colors.ENDC}")
       print(f"CDN URL: {outputs['ChatCDN']}")
       print(f"\nEmbed on your website:")
       print(f'<script src="{outputs["ChatCDN"]}"></script>')
       print(f'<amplify-chat conversation-id="my-site"></amplify-chat>')
   ```

5. **Handle --chat-only path:**

   Find the `--chat-only` section (around line 1061). Update similarly:

   ```python
   if args.chat_only:
       # ...existing code to get kb_id...

       # Get ConfigurationTable name
       stack_name = f"RAGStack-{args.project_name}"
       sam_outputs = get_stack_outputs(stack_name, args.region)
       config_table_name = sam_outputs.get('ConfigurationTableName')

       if not config_table_name:
           log_error("ConfigurationTableName not found in SAM stack outputs")
           sys.exit(1)

       # Deploy Amplify
       try:
           cdn_url = amplify_deploy(
               args.project_name,
               args.region,
               kb_id,
               artifact_bucket,  # Need to get this - see note below
               config_table_name
           )

           # Update chat_deployed flag
           seed_configuration_table(stack_name, args.region, chat_deployed=True)

           log_success(f"Chat CDN URL: {cdn_url}")
       except Exception as e:
           log_error(f"Amplify deployment failed: {e}")
           sys.exit(1)
   ```

   **Note:** For `--chat-only` path, we need to get the artifact bucket. Add before the `amplify_deploy()` call:

   ```python
   # Get or create artifact bucket
   try:
       artifact_bucket = create_sam_artifact_bucket(args.project_name, args.region)
   except IOError as e:
       log_error(f"Failed to access artifact bucket: {e}")
       sys.exit(1)
   ```

### Verification Checklist

- [ ] `--deploy-chat` path extracts KB ID and ConfigurationTable name
- [ ] Calls `amplify_deploy()` with 5 parameters
- [ ] Sets `chat_deployed=True` after successful deployment
- [ ] Adds CDN URL to outputs dict
- [ ] `print_outputs()` displays chat CDN URL and embed code
- [ ] `--chat-only` path handles artifact bucket and calls correctly
- [ ] No syntax errors: `python -m py_compile publish.py`

### Commit

```bash
git add publish.py
git commit -m "feat(publish): integrate Amplify chat deployment into main flow

- Extract KB ID and ConfigurationTable name from SAM outputs
- Pass all required parameters to amplify_deploy
- Set chat_deployed=True after successful deployment
- Display CDN URL and embed code in deployment outputs
- Handle both --deploy-chat and --chat-only paths
- Update print_outputs to show chat component information"
```

---

## Phase 3 Complete - Verification

Before moving to Phase 4, verify:

### Checklist

- [ ] All commits made with conventional commit format
- [ ] TypeScript in `amplify/backend.ts` compiles: `cd amplify && npx tsc --noEmit`
- [ ] Python syntax valid: `python -m py_compile publish.py`
- [ ] Phase 1's packaging function unchanged
- [ ] Phase 2's web component structure matches CodeBuild expectations

### Integration Test (Full Deployment)

**Prerequisites:**
- Existing SAM deployment OR run `python publish.py --project-name test-chat --admin-email admin@example.com --region us-east-1` first
- AWS credentials configured
- ~30 minutes for full deployment

**Test Deployment:**

```bash
# Full deployment with chat
python publish.py \
  --project-name test-chat \
  --admin-email your-email@example.com \
  --region us-east-1 \
  --deploy-chat

# Expected output at end:
# ========================================
# Deployment Complete! (Project: test-chat)
# ========================================
#
# Admin UI: https://d1111.cloudfront.net
# GraphQL API: https://abc123.appsync-api.us-east-1.amazonaws.com/graphql
# Chat Component:
# CDN URL: https://d2222.cloudfront.net/amplify-chat.js
#
# Embed on your website:
# <script src="https://d2222.cloudfront.net/amplify-chat.js"></script>
# <amplify-chat conversation-id="my-site"></amplify-chat>
```

**Verify Resources Created:**

```bash
# Check Amplify stack
aws cloudformation describe-stacks \
  --stack-name $(aws cloudformation list-stacks --query 'StackSummaries[?starts_with(StackName, `amplify-`)].StackName' --output text | head -1) \
  --region us-east-1

# Check S3 bucket
aws s3 ls | grep webcomponentassets

# Check CodeBuild project
aws codebuild list-projects --region us-east-1 | grep web-component

# Check CloudFront distribution
aws cloudfront list-distributions --query 'DistributionList.Items[?Comment==`CDN for Amplify Chat web component`]'
```

**Verify CodeBuild Ran:**

```bash
# Get build project name from outputs
PROJECT_NAME=$(aws cloudformation describe-stacks --stack-name amplify-* --query 'Stacks[0].Outputs[?OutputKey==`BuildProjectName`].OutputValue' --output text --region us-east-1)

# Check recent builds
aws codebuild list-builds-for-project --project-name $PROJECT_NAME --region us-east-1

# Get latest build logs
BUILD_ID=$(aws codebuild list-builds-for-project --project-name $PROJECT_NAME --query 'ids[0]' --output text --region us-east-1)
aws codebuild batch-get-builds --ids $BUILD_ID --region us-east-1 --query 'builds[0].buildStatus'
```

**Test Web Component:**

Create `test.html`:
```html
<!DOCTYPE html>
<html>
<head>
  <title>Test Amplify Chat</title>
</head>
<body>
  <h1>Amplify Chat Test</h1>

  <!-- Replace with your actual CDN URL -->
  <script src="https://d2222.cloudfront.net/amplify-chat.js"></script>

  <amplify-chat
    conversation-id="test"
    header-text="Test Chat"
  ></amplify-chat>
</body>
</html>
```

Open in browser and verify:
- [ ] Script loads without errors
- [ ] `<amplify-chat>` element renders
- [ ] Chat UI displays (may not be functional yet - Phase 4 adds backend logic)

---

## Common Issues

**Issue:** `amplify_outputs.json not found`
- **Solution:** Ensure `npx ampx deploy` completed. Check for errors in deploy logs.

**Issue:** CodeBuild fails with "Access Denied" to source bucket
- **Solution:** Verify IAM policy in backend.ts grants access to `ragstack-*-artifacts-*`

**Issue:** CloudFront invalidation fails
- **Solution:** Verify IAM policy grants `cloudfront:CreateInvalidation`

**Issue:** Web component not found at CDN URL (404)
- **Solution:** Check CodeBuild logs - build may have failed. Manually trigger build in console.

**Issue:** `ConfigurationTableName` not found in SAM outputs
- **Solution:** Ensure SAM template.yaml exports ConfigurationTable name. Check `Outputs` section.

---

## Handoff to Phase 4

**What you've delivered:**
- ✅ CDN infrastructure in Amplify backend (S3, CloudFront, CodeBuild)
- ✅ Amplify config generation with table name and source location
- ✅ Full deployment integration in publish.py
- ✅ CDN URL output after deployment
- ✅ Web component deployed to CloudFront

**What Phase 4 will do:**
- Implement conversation handler Lambda in Amplify
- Read configuration from ConfigurationTable
- Implement rate limiting with quota tracking
- Implement model degradation logic
- Handle authentication (optional userId/userToken)

**Current State:**
- Web component is deployed and embeddable
- No backend logic yet (conversations won't work)
- ConfigurationTable seeded with chat defaults
- Phase 4 connects the runtime behavior

---

**Next:** [Phase-4.md](Phase-4.md) - Amplify Runtime Logic (Conversation Handler, Config Reading, Rate Limiting)
