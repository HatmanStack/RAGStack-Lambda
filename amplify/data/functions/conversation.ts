/**
 * Conversation Handler for Amplify Chat
 *
 * This Lambda function:
 * 1. Reads configuration from SAM's ConfigurationTable
 * 2. Validates authentication if required
 * 3. Checks quotas and selects model (primary or fallback)
 * 4. Queries Bedrock Knowledge Base
 * 5. Extracts sources from citations
 * 6. Increments usage quotas
 * 7. Returns response with content, sources, modelUsed
 */

import type { Schema } from '../resource';
import { DynamoDBClient, GetItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { BedrockAgentRuntimeClient, RetrieveAndGenerateCommand } from '@aws-sdk/client-bedrock-agent-runtime';
import { KNOWLEDGE_BASE_CONFIG } from '../config';

/**
 * Config cache (60s TTL to minimize DynamoDB reads)
 */
let cachedConfig: ChatConfig | null = null;
let cacheTime = 0;
const CACHE_TTL_MS = 60000; // 60 seconds

/**
 * Chat configuration structure
 */
interface ChatConfig {
  requireAuth: boolean;
  primaryModel: string;
  fallbackModel: string;
  globalQuotaDaily: number;
  perUserQuotaDaily: number;
}

/**
 * Main handler function
 */
export const handler: Schema['conversation']['functionHandler'] = async (event) => {
  const { message, conversationId, userId, userToken } = event.arguments;

  console.log('Conversation request:', {
    conversationId,
    userId: userId || 'anonymous',
    messageLength: message?.length || 0,
  });

  try {
    // Step 1: Load configuration
    const config = await getChatConfig();

    // Step 2: Validate authentication if required
    if (config.requireAuth && (!userId || !userToken)) {
      throw new Error('Authentication required. Please provide userId and userToken.');
    }

    // AUTHENTICATION LIMITATION:
    // This implementation checks token PRESENCE but does NOT validate token authenticity.
    // Security model: "Trust but track" - we trust parent app's auth, track usage per userId.
    //
    // Production implementation options:
    // A) JWT Validation: Verify token signature if parent app uses JWT
    //    import { CognitoJwtVerifier } from 'aws-jwt-verify';
    //    const verifier = CognitoJwtVerifier.create({ userPoolId: '...' });
    //    await verifier.verify(userToken); // Throws if invalid
    //
    // B) API Key Validation: Check against allowlist in ConfigurationTable
    //    const validTokens = await getValidApiKeys();
    //    if (!validTokens.includes(userToken)) throw new Error('Invalid API key');
    //
    // C) OAuth Token Introspection: Call parent app's auth service
    //    const response = await fetch('https://auth-service/introspect', {
    //      headers: { Authorization: `Bearer ${userToken}` }
    //    });
    //    if (!response.ok) throw new Error('Invalid token');
    //
    // Current approach is suitable for:
    // - Trusted environments where parent app controls embedding
    // - Usage tracking without strict security (anonymous + optional userId)
    // - Cost control via quotas (primary security mechanism)
    //
    // For production with strict auth requirements, implement option A, B, or C above.

    // Step 3: Select model based on quotas
    const trackingId = userId || `anon:${conversationId}`;
    const selectedModel = await selectModelBasedOnQuotas(trackingId, config, !!userId);

    console.log('Selected model:', selectedModel);

    // Step 4: Query Bedrock Knowledge Base
    const response = await queryKnowledgeBase(
      message,
      conversationId,
      selectedModel,
      KNOWLEDGE_BASE_CONFIG.knowledgeBaseId,
      KNOWLEDGE_BASE_CONFIG.region
    );

    // Step 5: Increment quotas (only if using primary model)
    if (selectedModel === config.primaryModel) {
      await incrementQuotas(trackingId, !!userId);
    }

    // Step 6: Return response
    console.log('Conversation response:', {
      conversationId,
      contentLength: response.content.length,
      sourcesCount: response.sources?.length || 0,
      modelUsed: response.modelUsed,
    });

    return response;

  } catch (error) {
    console.error('Conversation handler error:', error);
    throw error;
  }
};

/**
 * Get chat configuration from ConfigurationTable with caching
 */
async function getChatConfig(): Promise<ChatConfig> {
  // Return cached config if still valid
  const now = Date.now();
  if (cachedConfig && (now - cacheTime < CACHE_TTL_MS)) {
    console.log('Using cached config');
    return cachedConfig;
  }

  console.log('Fetching config from DynamoDB...');

  const dynamodb = new DynamoDBClient({ region: KNOWLEDGE_BASE_CONFIG.region });

  try {
    const result = await dynamodb.send(
      new GetItemCommand({
        TableName: KNOWLEDGE_BASE_CONFIG.configurationTableName,
        Key: { Configuration: { S: 'Default' } },
      })
    );

    if (!result.Item) {
      throw new Error('Configuration not found in ConfigurationTable');
    }

    // Parse config from DynamoDB item
    const config: ChatConfig = {
      requireAuth: result.Item.chat_require_auth?.BOOL ?? false,
      primaryModel: result.Item.chat_primary_model?.S ?? 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
      fallbackModel: result.Item.chat_fallback_model?.S ?? 'us.amazon.nova-micro-v1:0',
      globalQuotaDaily: parseInt(result.Item.chat_global_quota_daily?.N ?? '10000'),
      perUserQuotaDaily: parseInt(result.Item.chat_per_user_quota_daily?.N ?? '100'),
    };

    // Update cache
    cachedConfig = config;
    cacheTime = now;

    console.log('Config loaded:', config);
    return config;

  } catch (error) {
    console.error('Error fetching config:', error);
    throw new Error(`Failed to load configuration: ${error}`);
  }
}

// Additional functions will be implemented in Task 3
async function selectModelBasedOnQuotas(trackingId: string, config: ChatConfig, isAuthenticated: boolean): Promise<string> {
  // TODO: Implement in Task 3
  return config.primaryModel;
}

async function queryKnowledgeBase(message: string, conversationId: string, model: string, kbId: string, region: string): Promise<any> {
  // TODO: Implement in Task 3
  return { content: 'TODO', sources: [], modelUsed: model };
}

async function incrementQuotas(trackingId: string, isAuthenticated: boolean): Promise<void> {
  // TODO: Implement in Task 3
}
