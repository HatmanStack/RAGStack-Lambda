/**
 * AWS Configuration
 *
 * This file contains AWS resource configuration for document pipeline UI.
 * Values are populated from CloudFormation outputs after deployment.
 *
 * To update after deployment:
 * 1. Deploy CloudFormation stack: sam deploy
 * 2. Run configuration script: ./scripts/configure_ui.sh <stack-name>
 * 3. Start dev server: cd src/ui && npm start
 *
 * Or manually create .env.local with these variables.
 */

const awsConfig = {
  // AWS Region
  region: import.meta.env.VITE_AWS_REGION || 'us-east-1',

  // Cognito Authentication
  Auth: {
    Cognito: {
      userPoolId: import.meta.env.VITE_USER_POOL_ID || '',
      userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID || '',
      identityPoolId: import.meta.env.VITE_IDENTITY_POOL_ID || '',
      loginWith: {
        email: true,
      },
      signUpVerificationMethod: 'code',
      userAttributes: {
        email: {
          required: true,
        },
      },
      allowGuestAccess: false,
      passwordFormat: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireNumbers: true,
        requireSpecialCharacters: true,
      },
    },
  },

  // AppSync GraphQL API
  API: {
    GraphQL: {
      endpoint: import.meta.env.VITE_GRAPHQL_URL || '',
      region: import.meta.env.VITE_AWS_REGION || 'us-east-1',
      defaultAuthMode: 'userPool',
    },
  },

  // S3 Storage for uploads (uses input/ prefix)
  Storage: {
    S3: {
      bucket: import.meta.env.VITE_DATA_BUCKET || '',
      region: import.meta.env.VITE_AWS_REGION || 'us-east-1',
    },
  },
};

// Debug: Log configuration (sanitized)

export default awsConfig;
