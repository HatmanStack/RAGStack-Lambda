/**
 * ChatWithSources Component
 *
 * A reusable, embeddable chat component that wraps Amplify's <AIConversation>
 * and adds custom source/citation display below responses.
 *
 * This component is designed to be embedded in multiple applications.
 * It does NOT include authentication - parent app handles auth via Authenticator.
 *
 * Usage:
 * ```tsx
 * import { ChatWithSources } from '@your-org/amplify-chat';
 *
 * <Authenticator> {// Your auth wrapper}
 *   <ChatWithSources
 *     conversationId="my-chat-1"
 *     headerText="Ask me anything"
 *   />
 * </Authenticator>
 * ```
 */

import React, { useCallback, useMemo, useEffect, useRef } from 'react';
// Temporarily commented out - requires backend AI configuration
// import { AIConversation } from '@aws-amplify/ui-react-ai';
import { SourcesDisplay } from './SourcesDisplay';
import { ChatWithSourcesProps, Source } from '../types';
import { applyTheme, type ThemePreset, type ThemeOverrides } from '../styles/themes';
import styles from '../styles/ChatWithSources.module.css';

/**
 * Custom response component that renders AI responses with sources
 *
 * This component is passed to <AIConversation> as the responseComponent prop.
 * It receives the message text and sources, then renders them with styling.
 */
const ResponseComponent = React.memo(
  ({ message, sources }: { message: string; sources?: Source[] }) => (
    <div className={styles.responseContainer}>
      <p className={styles.responseText}>{message}</p>
      {sources && sources.length > 0 && (
        <SourcesDisplay sources={sources} />
      )}
    </div>
  )
);

ResponseComponent.displayName = 'ResponseComponent';

/**
 * ChatWithSources Component
 *
 * Main embeddable chat interface that:
 * - Wraps Amplify's <AIConversation> component
 * - Displays sources/citations below responses
 * - Handles message state and streaming
 * - Provides hooks for parent app to track messages
 *
 * @param props - Component configuration
 * @returns React component rendering the chat interface
 *
 * @example
 * ```tsx
 * <ChatWithSources
 *   conversationId="chat-1"
 *   headerText="Document Q&A"
 *   showSources={true}
 *   onSendMessage={(msg, convId) => console.log('Sent:', msg)}
 * />
 * ```
 */
export const ChatWithSources: React.FC<ChatWithSourcesProps> = ({
  conversationId = 'default',
  className,
  headerText = 'Document Q&A',
  headerSubtitle = 'Ask questions about your documents',
  inputPlaceholder = 'Ask a question...',
  onSendMessage,
  onResponseReceived,
  showSources = true,
  maxWidth = '100%',
  userId = null,
  userToken = null,
  themePreset = 'light',
  themeOverrides,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Apply theme on mount and when theme changes
  // Scope theme to this component instance to prevent conflicts
  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    applyTheme(
      themePreset as ThemePreset,
      themeOverrides as ThemeOverrides,
      containerRef.current
    );
  }, [themePreset, themeOverrides]);
  // Memoize callbacks to prevent unnecessary re-renders
  const handleSendMessage = useCallback(
    (message: string) => {
      if (onSendMessage) {
        onSendMessage(message, conversationId);
      }
    },
    [onSendMessage, conversationId]
  );

  const handleResponseReceived = useCallback(
    (response: any) => {
      if (onResponseReceived && response) {
        // Transform response data if needed
        const chatMessage = {
          role: 'assistant' as const,
          content: response.message || response.content || '',
          sources: response.sources || [],
          timestamp: new Date().toISOString(),
          modelUsed: response.modelUsed,
        };
        onResponseReceived(chatMessage);
      }
    },
    [onResponseReceived]
  );

  // Memoize container style
  const containerStyle = useMemo(
    () => ({ maxWidth, width: '100%' }),
    [maxWidth]
  );

  return (
    <div
      ref={containerRef}
      className={`${styles.chatContainer} ${className || ''}`}
      style={containerStyle}
    >
      {/* Header Section */}
      <div className={styles.chatHeader}>
        <h1 className={styles.headerTitle}>{headerText}</h1>
        {headerSubtitle && (
          <p className={styles.headerSubtitle}>{headerSubtitle}</p>
        )}
      </div>

      {/* Chat Content */}
      <div className={styles.chatContent}>
        {/* Temporary placeholder - AIConversation requires backend AI configuration */}
        <div style={{ padding: '20px', textAlign: 'center', background: '#f9f9f9', borderRadius: '8px' }}>
          <h3 style={{ color: '#4CAF50', marginBottom: '10px' }}>✅ Web Component Loaded Successfully!</h3>
          <p style={{ marginBottom: '5px' }}>Conversation ID: <strong>{conversationId}</strong></p>
          <p style={{ marginBottom: '5px' }}>User ID: <strong>{userId || 'Not set'}</strong></p>
          <p style={{ marginBottom: '15px' }}>Show Sources: <strong>{showSources ? 'Yes' : 'No'}</strong></p>

          <div style={{ marginTop: '20px', padding: '15px', background: '#fff3cd', borderRadius: '8px', border: '1px solid #ffc107' }}>
            <p style={{ fontWeight: 'bold', marginBottom: '10px' }}>⚠️ AIConversation Backend Setup Required:</p>
            <ul style={{ textAlign: 'left', display: 'inline-block', margin: 0 }}>
              <li>GraphQL schema with AI conversation types</li>
              <li>Lambda resolvers for Bedrock integration</li>
              <li>Amplify AI Kit configuration</li>
            </ul>
            <p style={{ marginTop: '15px', fontSize: '14px', color: '#666' }}>
              This placeholder confirms the web component infrastructure is working.
              Replace with proper AIConversation once backend is configured.
            </p>
          </div>
        </div>
      </div>

      {/* Footer Section */}
      <div className={styles.chatFooter}>
        <p className={styles.footerText}>
          Responses are sourced from your knowledge base
        </p>
      </div>
    </div>
  );
};

export default ChatWithSources;
