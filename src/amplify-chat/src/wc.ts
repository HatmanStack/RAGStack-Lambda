/**
 * Web Component Bundle Entry Point
 *
 * This file is used to build a UMD bundle that can be used with a script tag.
 * It includes the Web Component and all dependencies needed for standalone use.
 *
 * Build with: npm run build:wc
 *
 * Usage:
 * ```html
 * <script src="https://your-cdn.com/amplify-chat.js"></script>
 * <script>
 *   // Configure Amplify before using the component
 *   window.AmplifyConfig = {
 *     API: {
 *       GraphQL: {
 *         endpoint: 'https://xxx.appsync-api.amazonaws.com/graphql',
 *         region: 'us-east-1',
 *         defaultAuthMode: 'userPool'
 *       }
 *     },
 *     Auth: {
 *       Cognito: {
 *         userPoolId: 'us-east-1_xxx',
 *         userPoolClientId: 'xxx'
 *       }
 *     }
 *   };
 * </script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 * ```
 *
 * Or fetch config from your API:
 * ```html
 * <script src="https://your-cdn.com/amplify-chat.js"></script>
 * <amplify-chat
 *   conversation-id="my-chat"
 *   config-url="/api/chat-config"
 * ></amplify-chat>
 * ```
 */

import { Amplify } from 'aws-amplify';
import { AMPLIFY_OUTPUTS } from './amplify-config.generated';

// Configure Amplify (bundled config takes precedence over window config)
if (AMPLIFY_OUTPUTS) {
  // Use bundled configuration (zero-config mode)
  Amplify.configure(AMPLIFY_OUTPUTS);
  console.debug('[AmplifyChat] Configured with bundled config');
} else if (typeof window !== 'undefined' && (window as any).AmplifyConfig) {
  // Use runtime configuration from window.AmplifyConfig
  Amplify.configure((window as any).AmplifyConfig);
  console.debug('[AmplifyChat] Configured with window.AmplifyConfig');
} else {
  // No configuration found - user must set window.AmplifyConfig
  console.warn('[AmplifyChat] No configuration found. Set window.AmplifyConfig before using the component.');
}

// Export the Web Component
export { AmplifyChat } from './components/AmplifyChat.wc';

// Export types for TypeScript users
export type {
  ChatWithSourcesProps,
  SourcesDisplayProps,
  Source,
  ChatMessage,
  BedrockCitation,
} from './types';

// Register globally for easy access
declare global {
  namespace JSX {
    interface IntrinsicElements {
      'amplify-chat': React.DetailedHTMLProps<
        React.HTMLAttributes<HTMLElement> & {
          'conversation-id'?: string;
          'header-text'?: string;
          'header-subtitle'?: string;
          'show-sources'?: boolean;
          'max-width'?: string;
        },
        HTMLElement
      >;
    }
  }
}

// Version
export const VERSION = '1.0.0';
