/**
 * Web Component Bundle Entry Point
 *
 * This file is used to build an IIFE bundle that can be used with a script tag.
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
try {
  Amplify.configure(AMPLIFY_OUTPUTS);
  console.log('[AmplifyChat] Amplify configured successfully');
} catch (error) {
  console.error('[AmplifyChat] Failed to configure Amplify:', error);
  console.error('[AmplifyChat] AMPLIFY_OUTPUTS:', AMPLIFY_OUTPUTS);
}

// Import and auto-register the Web Component
// The import side effect will register the custom element
import { AmplifyChat } from './components/AmplifyChat.wc';

// Force registration in case it didn't happen during import
// (this is safe because customElements.define() is idempotent if already defined)
if (!customElements.get('amplify-chat')) {
  try {
    customElements.define('amplify-chat', AmplifyChat);
    console.log('[AmplifyChat] Custom element registered successfully');
  } catch (error) {
    console.error('[AmplifyChat] Failed to register custom element:', error);
  }
}

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
