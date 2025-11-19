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
import { mapToOriginalDocument } from './mapToOriginalDocument';
import type { ChatConfig } from './types';

/**
 * Config cache (60s TTL to minimize DynamoDB reads)
 */
let cachedConfig: ChatConfig | null = null;
let cacheTime = 0;
const CACHE_TTL_MS = 60000; // 60 seconds

/**
 * Main handler function
 */
export const handler: Schema['conversation']['functionHandler'] = async (event) => {
  const { message, conversationId, userId, userToken } = event.arguments;

  // Get authenticated user context from Lambda Authorizer (if auth enabled)
  const authContext = (event as any).identity?.resolverContext;
  const authenticatedUserId = authContext?.userId;
  const username = authContext?.username;

  console.log('Conversation request:', {
    conversationId,
    requestedUserId: userId || 'anonymous',
    authenticatedUserId: authenticatedUserId || 'none',
    username: username || 'anonymous',
    messageLength: message?.length || 0,
  });

  try {
    // Step 1: Load configuration
    const config = await getChatConfig();

    // Step 2: Validate authentication if required
    // Note: Lambda Authorizer has already validated the JWT token
    // We just check if auth is required and if we have an authenticated user
    if (config.requireAuth) {
      if (!authenticatedUserId) {
        throw new Error(
          'Authentication required. Please provide a valid authentication token in the Authorization header.'
        );
      }

      // Verify userId from arguments matches authenticated user (if provided)
      if (userId && userId !== authenticatedUserId) {
        throw new Error('User ID mismatch. Provided userId does not match authenticated user.');
      }

      console.log('User authenticated via Lambda Authorizer:', {
        userId: authenticatedUserId,
        username,
      });
    }

    // Step 3: Atomically check and increment quotas
    // Use authenticated userId if available, otherwise fallback to requested userId or anonymous
    const trackingId = authenticatedUserId || userId || `anon:${conversationId}`;
    const isAuthenticated = !!authenticatedUserId;
    const selectedModel = await atomicQuotaCheckAndIncrement(trackingId, config, isAuthenticated);

    console.log('Selected model:', selectedModel);

    // Step 4: Query Bedrock Knowledge Base
    const response = await queryKnowledgeBase(
      message,
      conversationId,
      selectedModel,
      process.env.KNOWLEDGE_BASE_ID!,
      process.env.AWS_REGION!,
      config
    );

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
export async function getChatConfig(): Promise<ChatConfig> {
  // Return cached config if still valid
  const now = Date.now();
  if (cachedConfig && (now - cacheTime < CACHE_TTL_MS)) {
    console.log('Using cached config');
    return cachedConfig;
  }

  console.log('Fetching config from DynamoDB...');

  const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION! });

  try {
    const result = await dynamodb.send(
      new GetItemCommand({
        TableName: process.env.CONFIGURATION_TABLE_NAME!,
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
      allowDocumentAccess: result.Item.chat_allow_document_access?.BOOL ?? false,
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

/**
 * Atomically check quotas and increment if within limits
 *
 * Uses conditional DynamoDB writes to prevent race conditions.
 * If quota is exceeded, returns fallback model.
 * If within quota, increments atomically and returns primary model.
 *
 * This fixes the race condition where multiple concurrent requests could
 * bypass quota limits by reading stale values before incrementing.
 *
 * Quota keys in DynamoDB:
 * - Global: quota#global#{YYYY-MM-DD}
 * - Per-user: quota#user#{userId}#{YYYY-MM-DD}
 */
export async function atomicQuotaCheckAndIncrement(
  trackingId: string,
  config: ChatConfig,
  isAuthenticated: boolean
): Promise<string> {
  const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION! });
  const today = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
  const ttl = Math.floor(Date.now() / 1000) + (86400 * 2); // 2 days from now

  try {
    // Try to atomically increment global quota with condition
    const globalKey = `quota#global#${today}`;

    try {
      const globalResult = await dynamodb.send(
        new UpdateItemCommand({
          TableName: process.env.CONFIGURATION_TABLE_NAME!,
          Key: { Configuration: { S: globalKey } },
          UpdateExpression: 'ADD #count :inc SET #ttl = :ttl',
          ConditionExpression: '#count < :limit OR attribute_not_exists(#count)',
          ExpressionAttributeNames: {
            '#count': 'count',
            '#ttl': 'ttl',
          },
          ExpressionAttributeValues: {
            ':inc': { N: '1' },
            ':limit': { N: config.globalQuotaDaily.toString() },
            ':ttl': { N: ttl.toString() },
          },
          ReturnValues: 'ALL_NEW',
        })
      );

      const newGlobalCount = parseInt(globalResult.Attributes?.count?.N ?? '0');
      console.log(`Global quota incremented: ${newGlobalCount}/${config.globalQuotaDaily}`);

    } catch (error: any) {
      // ConditionalCheckFailedException means quota exceeded
      if (error.name === 'ConditionalCheckFailedException') {
        console.log('Global quota exceeded, using fallback model');
        return config.fallbackModel;
      }
      throw error; // Re-throw other errors
    }

    // Try to atomically increment per-user quota (if authenticated)
    if (isAuthenticated) {
      const userKey = `quota#user#${trackingId}#${today}`;

      try {
        const userResult = await dynamodb.send(
          new UpdateItemCommand({
            TableName: process.env.CONFIGURATION_TABLE_NAME!,
            Key: { Configuration: { S: userKey } },
            UpdateExpression: 'ADD #count :inc SET #ttl = :ttl',
            ConditionExpression: '#count < :limit OR attribute_not_exists(#count)',
            ExpressionAttributeNames: {
              '#count': 'count',
              '#ttl': 'ttl',
            },
            ExpressionAttributeValues: {
              ':inc': { N: '1' },
              ':limit': { N: config.perUserQuotaDaily.toString() },
              ':ttl': { N: ttl.toString() },
            },
            ReturnValues: 'ALL_NEW',
          })
        );

        const newUserCount = parseInt(userResult.Attributes?.count?.N ?? '0');
        console.log(`User quota incremented for ${trackingId}: ${newUserCount}/${config.perUserQuotaDaily}`);

      } catch (error: any) {
        // ConditionalCheckFailedException means quota exceeded
        if (error.name === 'ConditionalCheckFailedException') {
          // Need to decrement global quota since user quota failed
          await dynamodb.send(
            new UpdateItemCommand({
              TableName: process.env.CONFIGURATION_TABLE_NAME!,
              Key: { Configuration: { S: globalKey } },
              UpdateExpression: 'ADD #count :dec',
              ExpressionAttributeNames: {
                '#count': 'count',
              },
              ExpressionAttributeValues: {
                ':dec': { N: '-1' },
              },
            })
          );

          console.log('User quota exceeded, using fallback model (global quota rolled back)');
          return config.fallbackModel;
        }
        throw error; // Re-throw other errors
      }
    }

    // Both quotas incremented successfully - use primary model
    return config.primaryModel;

  } catch (error) {
    console.error('Error in atomic quota check:', error);
    // On error, default to fallback model (conservative approach)
    return config.fallbackModel;
  }
}

/**
 * Query Bedrock Knowledge Base and extract sources
 */
export async function queryKnowledgeBase(
  message: string,
  conversationId: string,
  modelArn: string,
  kbId: string,
  region: string,
  config: ChatConfig
): Promise<{ content: string; sources: any[]; modelUsed: string }> {
  const bedrock = new BedrockAgentRuntimeClient({ region });

  console.log('Querying Knowledge Base:', {
    kbId,
    model: modelArn,
    conversationId,
  });

  try {
    const response = await bedrock.send(
      new RetrieveAndGenerateCommand({
        input: { text: message },
        retrieveAndGenerateConfiguration: {
          type: 'KNOWLEDGE_BASE',
          knowledgeBaseConfiguration: {
            knowledgeBaseId: kbId,
            modelArn: modelArn,
          },
        },
        // sessionId: conversationId, // Disabled - causes validation errors when KB ID changes
      })
    );

    // Extract content
    const content = response.output?.text || 'No response generated';

    // Extract and format sources (now async with document URL mapping)
    const sources = await extractSources(response.citations || [], config);

    console.log('KB query successful:', {
      contentLength: content.length,
      sourcesCount: sources.length,
    });

    return {
      content,
      sources,
      modelUsed: modelArn,
    };

  } catch (error) {
    console.error('Bedrock query error:', error);
    throw new Error(`Knowledge Base query failed: ${error}`);
  }
}

/**
 * Extract sources from Bedrock citations
 *
 * Converts Bedrock citation format to our Source type.
 * Optionally includes presigned URLs for original documents when access is enabled.
 */
export async function extractSources(citations: any[], config: ChatConfig): Promise<any[]> {
  const sources: any[] = [];

  for (const citation of citations) {
    if (!citation.retrievedReferences) continue;

    for (const ref of citation.retrievedReferences) {
      // Extract S3 URI for document mapping
      const s3Uri = ref.location?.s3Location?.uri || '';

      // Extract location (chunk ID or metadata)
      const location = ref.metadata?.['x-amz-bedrock-kb-chunk-id'] || 'Page unknown';

      // Extract snippet
      const snippet = ref.content?.text || '';

      if (snippet && s3Uri) {
        sources.push({
          s3Uri,
          location,
          snippet: snippet.substring(0, 200), // Limit snippet length
        });
      }
    }
  }

  // Remove duplicates based on snippet
  const uniqueSources = sources.filter((source, index, self) =>
    index === self.findIndex((s) => s.snippet === source.snippet)
  );

  // Map to original documents and add presigned URLs (parallel execution)
  const enrichedSources = await Promise.all(
    uniqueSources.map(async (source) => {
      const { documentUrl, filename } = await mapToOriginalDocument(source.s3Uri, config);
      return {
        title: filename,
        location: source.location,
        snippet: source.snippet,
        documentUrl,
        documentAccessAllowed: config.allowDocumentAccess,
      };
    })
  );

  return enrichedSources;
}
