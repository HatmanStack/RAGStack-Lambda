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
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 * ```
 */

import { Amplify } from 'aws-amplify';
import { AMPLIFY_OUTPUTS } from './amplify-config.generated';

// Configure Amplify with bundled config (zero-config embedding)
Amplify.configure(AMPLIFY_OUTPUTS);

// Import and auto-register the Web Component
// The import side effect will register the custom element
import { AmplifyChat } from './components/AmplifyChat.wc';

// Export the Web Component class for programmatic use
export { AmplifyChat };

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
