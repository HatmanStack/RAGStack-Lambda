#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AmplifyBackendStack } from '../lib/backend-stack';

const app = new cdk.App();

// Get environment variables from CodeBuild or use defaults for local development
const projectName = process.env.PROJECT_NAME || 'ragstack-dev';
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID,
  region: process.env.AWS_REGION || process.env.CDK_DEFAULT_REGION || 'us-west-2',
};

new AmplifyBackendStack(app, `amplify-${projectName}-backend`, {
  env,
  stackName: `amplify-${projectName}-backend`,
  description: 'RAGStack Amplify Backend - Cognito Auth + AppSync GraphQL API',
});

app.synth();
