/**
 * Lambda Authorizer for Amplify GraphQL API
 *
 * Validates Cognito JWT tokens from SAM's User Pool.
 * Supports both authenticated and anonymous modes based on runtime configuration.
 *
 * Flow:
 * 1. Check ConfigurationTable for chat_require_auth setting
 * 2. If auth not required and no token provided, allow anonymous access
 * 3. If token provided, validate against SAM's Cognito User Pool
 * 4. If auth required and no valid token, deny access
 */

import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';
import { KNOWLEDGE_BASE_CONFIG } from '../config';

/**
 * Create verifier instance (reused across invocations)
 */
const verifier = CognitoJwtVerifier.create({
  userPoolId: process.env.USER_POOL_ID || KNOWLEDGE_BASE_CONFIG.userPoolId,
  clientId: process.env.USER_POOL_CLIENT_ID || KNOWLEDGE_BASE_CONFIG.userPoolClientId,
  tokenUse: 'access',
});

/**
 * DynamoDB client for reading configuration
 */
const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION || KNOWLEDGE_BASE_CONFIG.region });

/**
 * Config cache (60s TTL to minimize DynamoDB reads)
 */
let cachedAuthRequired: boolean | null = null;
let cacheTime = 0;
const CACHE_TTL_MS = 60000; // 60 seconds

/**
 * Get chat_require_auth setting from ConfigurationTable
 */
async function getAuthRequired(): Promise<boolean> {
  // Return cached value if still valid
  const now = Date.now();
  if (cachedAuthRequired !== null && (now - cacheTime < CACHE_TTL_MS)) {
    return cachedAuthRequired;
  }

  console.log('Fetching auth config from DynamoDB...');

  try {
    const result = await dynamodb.send(
      new GetItemCommand({
        TableName: process.env.CONFIGURATION_TABLE_NAME || KNOWLEDGE_BASE_CONFIG.configurationTableName,
        Key: { Configuration: { S: 'Default' } },
      })
    );

    if (!result.Item) {
      console.warn('Configuration not found, defaulting to auth required');
      return true; // Fail secure if config missing
    }

    // Parse requireAuth setting (default to false for backwards compatibility)
    const requireAuth = result.Item.chat_require_auth?.BOOL ?? false;

    // Update cache
    cachedAuthRequired = requireAuth;
    cacheTime = now;

    console.log('Auth config loaded:', { requireAuth });
    return requireAuth;

  } catch (error) {
    console.error('Error fetching config:', error);
    // Fail secure - require auth if we can't read config
    return true;
  }
}

/**
 * Lambda Authorizer Handler
 *
 * @param event - AppSync authorization event
 * @returns Authorization response with user context
 */
export const handler = async (event: any) => {
  console.log('Authorization request received');

  // Check if authentication is required
  const requireAuth = await getAuthRequired();

  // Extract token from Authorization header
  const token = event.authorizationToken?.replace('Bearer ', '');

  if (!token) {
    console.log('No authorization token provided');

    // If auth is not required, allow anonymous access
    if (!requireAuth) {
      console.log('Auth not required, allowing anonymous access');
      return {
        isAuthorized: true,
        resolverContext: {
          userId: null,
          isAnonymous: true,
        },
        deniedFields: [],
        ttlOverride: 300, // Cache for 5 minutes
      };
    }

    // Auth is required but no token provided - deny
    console.error('Auth required but no token provided');
    return {
      isAuthorized: false,
      resolverContext: {},
      deniedFields: [],
      ttlOverride: 0,
    };
  }

  // Token provided - validate it (regardless of requireAuth setting)
  // If someone provides a token, we should validate it
  try {
    // Verify token against SAM's Cognito User Pool
    const payload = await verifier.verify(token);

    console.log('Token verified successfully', {
      userId: payload.sub,
      username: payload['cognito:username'],
    });

    // Return authorization response with user context
    return {
      isAuthorized: true,
      resolverContext: {
        userId: payload.sub,
        username: payload['cognito:username'] || 'unknown',
        email: payload.email || '',
        groups: payload['cognito:groups'] || [],
        isAnonymous: false,
      },
      deniedFields: [],
      ttlOverride: 300, // Cache authorization for 5 minutes
    };

  } catch (error) {
    console.error('Token verification failed:', {
      error: error instanceof Error ? error.message : String(error),
      tokenPrefix: token.substring(0, 20),
    });

    return {
      isAuthorized: false,
      resolverContext: {},
      deniedFields: [],
      ttlOverride: 0,
    };
  }
};
