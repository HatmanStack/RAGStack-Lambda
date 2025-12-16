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
 * <script src="https://your-cdn.com/ragstack-chat.js"></script>
 * <ragstack-chat conversation-id="my-chat"></ragstack-chat>
 * ```
 */

console.log('[RagStackChat] Bundle loading...');

import { THEME_CONFIG } from './amplify-config.generated';

// Export theme config for use by web component
export { THEME_CONFIG };

// Import and auto-register the Web Component
// The import side effect will register the custom element
console.log('[RagStackChat] Importing RagStackChat component...');
import { RagStackChat } from './components/RagStackChat.wc';
console.log('[RagStackChat] RagStackChat component imported');

// Force registration in case it didn't happen during import
// (this is safe because customElements.define() is idempotent if already defined)
console.log('[RagStackChat] Checking custom element registration...');
const existingDef = customElements.get('ragstack-chat');
console.log('[RagStackChat] Existing definition:', existingDef ? 'FOUND' : 'NOT FOUND');

if (!existingDef) {
  try {
    console.log('[RagStackChat] Registering custom element...');
    customElements.define('ragstack-chat', RagStackChat);
    console.log('[RagStackChat] Custom element registered successfully');
  } catch (error) {
    console.error('[RagStackChat] Failed to register custom element:', error);
    throw error;
  }
} else {
  console.log('[RagStackChat] Custom element already registered');
}

// Export the Web Component class for programmatic use
export { RagStackChat };

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
      'ragstack-chat': React.DetailedHTMLProps<
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
    if (event.filename?.includes('ragstack-chat')) {
      console.error('[RagStackChat] Uncaught error:', {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
        error: event.error,
      });
    }
  });

  window.addEventListener('unhandledrejection', (event) => {
    console.error('[RagStackChat] Unhandled promise rejection:', {
      reason: event.reason,
      promise: event.promise,
    });
  });

  console.log('[RagStackChat] Error handlers registered');
}
