/**
 * Lambda Authorizer for Amplify GraphQL API
 *
 * Validates Cognito JWT tokens from SAM's User Pool.
 * This authorizer is used when chat_require_auth is enabled.
 *
 * Flow:
 * 1. Web component passes token in Authorization header
 * 2. Authorizer validates token against SAM's Cognito User Pool
 * 3. If valid, returns user context (userId, username, groups)
 * 4. GraphQL resolvers receive user context
 */

import { CognitoJwtVerifier } from 'aws-jwt-verify';
import { KNOWLEDGE_BASE_CONFIG } from '../config';

/**
 * Create verifier instance (reused across invocations)
 */
const verifier = CognitoJwtVerifier.create({
  userPoolId: KNOWLEDGE_BASE_CONFIG.userPoolId,
  clientId: KNOWLEDGE_BASE_CONFIG.userPoolClientId,
  tokenUse: 'access',
});

/**
 * Lambda Authorizer Handler
 *
 * @param event - AppSync authorization event
 * @returns Authorization response with user context
 */
export const handler = async (event: any) => {
  console.log('Authorization request received');

  // Extract token from Authorization header
  const token = event.authorizationToken?.replace('Bearer ', '');

  if (!token) {
    console.error('No authorization token provided');
    return {
      isAuthorized: false,
      resolverContext: {},
      deniedFields: [],
      ttlOverride: 0,
    };
  }

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
      },
      deniedFields: [],
      ttlOverride: 300, // Cache authorization for 5 minutes
    };

  } catch (error) {
    console.error('Token verification failed:', {
      error: error.message,
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
