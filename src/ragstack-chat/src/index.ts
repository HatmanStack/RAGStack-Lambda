/**
 * RagStack Chat Component Library
 *
 * A reusable, embeddable React component for AI chat with source attribution.
 * Integrates with AWS Bedrock Knowledge Base.
 *
 * Supports both React imports and Web Component usage.
 *
 * @packageDocumentation
 *
 * @example React Usage
 * ```tsx
 * import { ChatWithSources } from '@ragstack/ragstack-chat';
 *
 * export function MyApp() {
 *   return (
 *     <ChatWithSources
 *       conversationId="my-chat"
 *       headerText="Ask a Question"
 *     />
 *   );
 * }
 * ```
 *
 * @example Web Component Usage
 * ```html
 * <script src="https://your-cdn.com/ragstack-chat.js"></script>
 * <ragstack-chat conversation-id="my-chat"></ragstack-chat>
 * ```
 */

// Export React components
export { ChatWithSources } from './components/ChatWithSources';
export { SourcesDisplay } from './components/SourcesDisplay';

// Export Web Component
export { RagStackChat } from './components/RagStackChat.wc';

// Export types
export type {
  ChatWithSourcesProps,
  SourcesDisplayProps,
  Source,
  ChatMessage,
  BedrockCitation,
} from './types';

// Export conversation utilities
export {
  getOrCreateConversationId,
  clearConversationId,
  resetConversationId,
} from './utils/conversationId';

// Version - will be updated by build process
export const VERSION = '1.0.0';
