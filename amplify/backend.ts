import { defineBackend } from '@aws-amplify/backend';
import { Stack, CfnOutput, Duration, RemovalPolicy, Tags } from 'aws-cdk-lib';
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

/**
 * Get CDK context (passed from CodeBuild via --context flags)
 * Falls back to environment variables if context not set
 */
const getContext = (scope: Stack, key: string, defaultValue?: string): string => {
  return scope.node.tryGetContext(key) || process.env[key.toUpperCase()] || defaultValue || '';
};

/**
 * @see https://docs.amplify.aws/react/build-a-backend/ to add storage, functions, and more
 */
export const backend = defineBackend({
  auth,
  data,
});

// Create custom stack for web component CDN
const cdnStack = backend.createStack('web-component-cdn');

// Read deployment configuration from context
const projectName = getContext(cdnStack, 'projectName', 'ragstack');
const region = getContext(cdnStack, 'region', cdnStack.region);
const userPoolId = getContext(cdnStack, 'userPoolId', '');
const userPoolClientId = getContext(cdnStack, 'userPoolClientId', '');

// Validate required values
if (!userPoolId || !userPoolClientId) {
  throw new Error('USER_POOL_ID and USER_POOL_CLIENT_ID must be provided via context or environment');
}

console.log(`Deploying Amplify backend for project: ${projectName}`);

// Note: Amplify Gen 2 stack names are auto-generated and read-only
// Stack naming will use Amplify's default pattern
// Phase 2 will need to adapt to discover stacks by pattern matching

// Add tags for resource management and discovery
// Only tagging CDN stack as auth/data stacks are managed internally by Amplify
Tags.of(cdnStack).add('Project', projectName);
Tags.of(cdnStack).add('ManagedBy', 'CDK-Amplify');
Tags.of(cdnStack).add('DeployedBy', 'CodeBuild');
Tags.of(cdnStack).add('AmplifyStackType', 'cdn');

// Auth and data stacks use Amplify's auto-generated names
// Pattern: amplify-{backend-id}-{resource-type}-{hash}
// Phase 2 will discover them by name pattern: amplify-*-{auth|data}-*

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
          'cd src/amplify-chat',
          'npm ci',
        ],
      },
      build: {
        commands: [
          'echo "Building web component..."',
          'npm run build:wc',
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
// Use exact bucket ARN from environment variable set by publish.py
// This follows principle of least privilege instead of wildcard patterns
const sourceBucketName = process.env.WEB_COMPONENT_SOURCE_BUCKET || '*-artifacts-*';
buildProject.addToRolePolicy(
  new PolicyStatement({
    effect: Effect.ALLOW,
    actions: ['s3:GetObject', 's3:ListBucket'],
    resources: [
      `arn:aws:s3:::${sourceBucketName}`,
      `arn:aws:s3:::${sourceBucketName}/*`,
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

// Note: Conversation Lambda permissions should be granted via Amplify data resource
// or through the defineFunction configuration in data/resource.ts
// Direct access to data.resources.functions is not exposed in the public API

// Configuration table access and Bedrock permissions should be added to:
// amplify/data/functions/conversation.ts via defineFunction({ ... }) configuration
