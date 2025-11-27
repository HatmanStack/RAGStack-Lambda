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

console.log('[AmplifyChat] Bundle loading...');

import { Amplify } from 'aws-amplify';
import { AMPLIFY_OUTPUTS, THEME_CONFIG } from './amplify-config.generated';

// Export theme config for use by web component
export { THEME_CONFIG };

// Configure Amplify with bundled config (zero-config embedding)
try {
  console.log('[AmplifyChat] Configuring Amplify...');
  Amplify.configure(AMPLIFY_OUTPUTS);
  console.log('[AmplifyChat] Amplify configured successfully');
  console.log('[AmplifyChat] API Endpoint:', AMPLIFY_OUTPUTS.data?.url);
  console.log('[AmplifyChat] Auth Region:', AMPLIFY_OUTPUTS.auth?.aws_region);
} catch (error) {
  console.error('[AmplifyChat] Failed to configure Amplify:', error);
  console.error('[AmplifyChat] AMPLIFY_OUTPUTS:', AMPLIFY_OUTPUTS);
}

// Import and auto-register the Web Component
// The import side effect will register the custom element
console.log('[AmplifyChat] Importing AmplifyChat component...');
import { AmplifyChat } from './components/AmplifyChat.wc';
console.log('[AmplifyChat] AmplifyChat component imported');

// Force registration in case it didn't happen during import
// (this is safe because customElements.define() is idempotent if already defined)
console.log('[AmplifyChat] Checking custom element registration...');
const existingDef = customElements.get('amplify-chat');
console.log('[AmplifyChat] Existing definition:', existingDef ? 'FOUND' : 'NOT FOUND');

if (!existingDef) {
  try {
    console.log('[AmplifyChat] Registering custom element...');
    customElements.define('amplify-chat', AmplifyChat);
    console.log('[AmplifyChat] ✅ Custom element registered successfully');
  } catch (error) {
    console.error('[AmplifyChat] ❌ Failed to register custom element:', error);
    throw error;
  }
} else {
  console.log('[AmplifyChat] ✅ Custom element already registered');
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

// Setup global error handlers AFTER bundle loads successfully
// (Moved to end to avoid interfering with script loading)
if (typeof window !== 'undefined') {
  window.addEventListener('error', (event) => {
    if (event.filename?.includes('amplify-chat')) {
      console.error('[AmplifyChat] Uncaught error:', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error,
      });
    }
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[AmplifyChat] Unhandled promise rejection:', {
      reason: event.reason,
      promise: event.promise,
    });
  });

  console.log('[AmplifyChat] Error handlers registered');
}
