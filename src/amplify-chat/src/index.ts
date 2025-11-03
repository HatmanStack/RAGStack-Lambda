/**
 * Amplify Chat Component Library
 *
 * A reusable, embeddable React component for AI chat with source attribution.
 * Integrates with AWS Amplify AI Kit and Bedrock Knowledge Base.
 *
 * Supports both React imports and Web Component usage.
 *
 * @packageDocumentation
 *
 * @example React Usage
 * ```tsx
 * import { ChatWithSources } from '@ragstack/amplify-chat';
 *
 * export function MyApp() {
 *   return (
 *     <Authenticator>
 *       <ChatWithSources
 *         conversationId="my-chat"
 *         headerText="Ask a Question"
 *       />
 *     </Authenticator>
 *   );
 * }
 * ```
 *
 * @example Web Component Usage
 * ```html
 * <script src="https://your-cdn.com/amplify-chat.js"></script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 * ```
 */

// Export React components
export { ChatWithSources } from './components/ChatWithSources';
export { SourcesDisplay } from './components/SourcesDisplay';

// Export Web Component
export { AmplifyChat } from './components/AmplifyChat.wc';

// Export types
export type {
  ChatWithSourcesProps,
  SourcesDisplayProps,
  Source,
  ChatMessage,
  BedrockCitation,
} from './types';

// Version - will be updated by build process
export const VERSION = '1.0.0';
