import { defineBackend } from '@aws-amplify/backend';
import { PolicyStatement } from 'aws-cdk-lib/aws-iam';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { KNOWLEDGE_BASE_CONFIG } from './data/config';

/**
 * Amplify Gen 2 Backend - Auth and Data only
 *
 * Note: Web component CDN infrastructure (S3, CloudFront, CodeBuild) is managed
 * via SAM template (template.yaml) instead of Amplify backend to avoid
 * pipeline-deploy custom stack limitations.
 *
 * See docs/plans/ for migration details.
 *
 * @see https://docs.amplify.aws/react/build-a-backend/
 */
export const backend = defineBackend({
  auth,
  data,
});

// Grant Conversation Lambda access to DynamoDB config table and Bedrock Knowledge Base
const conversationLambda = backend.data.resources.functions.conversation;

// DynamoDB config table permissions
conversationLambda.addToRolePolicy(
  new PolicyStatement({
    actions: ['dynamodb:GetItem', 'dynamodb:UpdateItem'],
    resources: [`arn:aws:dynamodb:${KNOWLEDGE_BASE_CONFIG.region}:*:table/${KNOWLEDGE_BASE_CONFIG.configurationTableName}`],
  })
);

// Bedrock Knowledge Base permissions
conversationLambda.addToRolePolicy(
  new PolicyStatement({
    actions: ['bedrock:InvokeModel', 'bedrock:Retrieve', 'bedrock:RetrieveAndGenerate'],
    resources: ['*'], // Bedrock requires wildcard for some actions
  })
);
