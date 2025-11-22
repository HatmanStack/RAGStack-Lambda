/**
 * Shared Types for Amplify Chat Functions
 *
 * Common type definitions used across conversation handler and document mapping.
 */

/**
 * Chat configuration structure
 *
 * This configuration is stored in DynamoDB ConfigurationTable and cached
 * for 60 seconds to minimize reads.
 */
export interface ChatConfig {
  /** Require authentication for chat access */
  requireAuth: boolean;

  /** Primary Bedrock model ARN to use for chat */
  primaryModel: string;

  /** Fallback Bedrock model ARN (used when quota exceeded) */
  fallbackModel: string;

  /** Daily query limit for all users combined */
  globalQuotaDaily: number;

  /** Daily query limit per authenticated user */
  perUserQuotaDaily: number;

  /** Allow users to download original source documents via presigned URLs */
  allowDocumentAccess: boolean;
}

/**
 * Create a mock ChatConfig for testing
 *
 * Provides default values for all required fields, with optional overrides.
 */
export function createMockChatConfig(overrides?: Partial<ChatConfig>): ChatConfig {
  return {
    requireAuth: false,
    primaryModel: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    fallbackModel: 'us.amazon.nova-micro-v1:0',
    globalQuotaDaily: 10000,
    perUserQuotaDaily: 100,
    allowDocumentAccess: false,
    ...overrides,
  };
}
