/**
 * ChatWithSources Component
 *
 * A reusable, embeddable chat component that provides a complete AI chat interface
 * with custom source/citation display using AWS Bedrock Knowledge Base.
 *
 * This component is designed to be embedded in multiple applications.
 * Supports both authenticated and guest modes for flexible deployment.
 *
 * Usage:
 * ```tsx
 * import { ChatWithSources } from '@your-org/amplify-chat';
 *
 * <Authenticator> {// Optional auth wrapper for authenticated mode}
 *   <ChatWithSources
 *     conversationId="my-chat-1"
 *     headerText="Ask me anything"
 *     userId={user.id}
 *     userToken={user.token}
 *   />
 * </Authenticator>
 * ```
 */

import React, { useCallback, useMemo, useEffect, useRef } from 'react';
import { ChatInterface } from './ChatInterface';
import { ChatWithSourcesProps } from '../types';
import { applyTheme, type ThemePreset, type ThemeOverrides } from '../styles/themes';
import styles from '../styles/ChatWithSources.module.css';

/**
 * ChatWithSources Component
 *
 * Main embeddable chat interface that:
 * - Wraps custom ChatInterface component
 * - Provides header and footer UI chrome
 * - Applies theme configuration
 * - Forwards props and callbacks to ChatInterface
 * - Supports both authenticated and guest modes
 *
 * ChatInterface handles all chat logic, message state, and GraphQL integration.
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
 *   userId={user.id}
 *   userToken={user.token}
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
      containerRef.current,
      themePreset as ThemePreset,
      themeOverrides as ThemeOverrides
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
        <ChatInterface
          conversationId={conversationId}
          userId={userId}
          userToken={userToken}
          showSources={showSources}
          inputPlaceholder={inputPlaceholder}
          onSendMessage={handleSendMessage}
          onResponseReceived={handleResponseReceived}
        />
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
