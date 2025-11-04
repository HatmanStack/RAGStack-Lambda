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
import { KNOWLEDGE_BASE_CONFIG } from './data/config';

/**
 * @see https://docs.amplify.aws/react/build-a-backend/ to add storage, functions, and more
 */
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
