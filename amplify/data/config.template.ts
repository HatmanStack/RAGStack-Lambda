/**
 * Amplify Chat Backend Configuration Template
 *
 * This file provides a template for the auto-generated config.ts.
 * It is used for local testing and should not be edited directly for deployment.
 */

export const KNOWLEDGE_BASE_CONFIG = {
  knowledgeBaseId: 'VALID-KB-ID-FORMAT',
  region: 'us-east-1',
  configurationTableName: 'test-config-table',
  userPoolId: 'test-user-pool-id',
  userPoolClientId: 'test-user-pool-client-id',
  webComponentSourceBucket: 'test-bucket',
  webComponentSourceKey: 'test-key',
} as const;

export type KnowledgeBaseConfig = typeof KNOWLEDGE_BASE_CONFIG;
