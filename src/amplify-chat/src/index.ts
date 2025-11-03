/**
 * Amplify Chat Component Library
 *
 * A reusable, embeddable React component for AI chat with source attribution.
 * Integrates with AWS Amplify AI Kit and Bedrock Knowledge Base.
 *
 * @packageDocumentation
 *
 * @example
 * ```tsx
 * import { ChatWithSources } from '@your-org/amplify-chat';
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
 */

// Export components
export { ChatWithSources } from './components/ChatWithSources';
export { SourcesDisplay } from './components/SourcesDisplay';

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
