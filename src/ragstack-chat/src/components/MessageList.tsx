/**
 * MessageList Component
 *
 * Scrollable container that renders message history with auto-scroll and loading states.
 * Manages the scrollable viewport but NOT message state.
 */

import React, { useRef, useEffect } from 'react';
import { MessageListProps } from '../types';
import { MessageBubble } from './MessageBubble';
import styles from '../styles/ChatWithSources.module.css';

/**
 * MessageList Component
 *
 * Displays a list of messages with auto-scroll to bottom, loading indicator,
 * error handling, and empty state.
 *
 * @param messages - Array of messages to display
 * @param isLoading - Loading indicator state
 * @param error - Error state (if any)
 * @param showSources - Whether to show sources for assistant messages
 */
export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  error,
  showSources = true,
}) => {
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    if (endOfMessagesRef.current) {
      endOfMessagesRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isLoading]);

  return (
    <div
      className={styles.messageListContainer}
      role="log"
      aria-live="polite"
      aria-busy={isLoading}
      aria-label="Chat message history"
    >
      {/* Empty state */}
      {messages.length === 0 && !isLoading && !error && (
        <div className={styles.emptyState} role="status" aria-live="polite">
          <p>Start a conversation by typing a message below.</p>
        </div>
      )}

      {/* Messages */}
      {messages.length > 0 && (
        <div className={styles.messagesContainer}>
          {messages.map((message, index) => (
            <MessageBubble
              key={`${message.timestamp}-${index}`}
              message={message}
              showSources={showSources}
            />
          ))}
        </div>
      )}

      {/* Loading indicator */}
      {isLoading && (
        <div className={styles.loadingIndicator} role="status" aria-live="polite">
          <span className={styles.loadingText}>Assistant is typing</span>
          <span className={styles.loadingDots} aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
        </div>
      )}

      {/* Error message */}
      {error && (
        <div className={styles.errorBubble} role="alert" aria-live="assertive">
          <div className={styles.errorIcon} aria-hidden="true">
            ⚠️
          </div>
          <div className={styles.errorMessage}>{error.message}</div>
          {error.retryable && error.onRetry && (
            <button
              className={styles.retryButton}
              onClick={error.onRetry}
              type="button"
              aria-label="Retry sending message"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {/* Scroll anchor */}
      <div ref={endOfMessagesRef} aria-hidden="true" />
    </div>
  );
};

