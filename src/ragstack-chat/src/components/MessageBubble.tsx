/**
 * MessageBubble Component
 *
 * Renders individual messages with role-based styling and source display.
 * Purely presentational - receives a ChatMessage and renders it.
 */

import React from 'react';
import { MessageBubbleProps } from '../types';
import { SourcesDisplay } from './SourcesDisplay';
import styles from '../styles/ChatWithSources.module.css';

/**
 * MessageBubble Component
 *
 * Displays a single message with appropriate styling based on role (user/assistant).
 * Integrates with existing SourcesDisplay component for assistant messages.
 *
 * @param message - The message to display
 * @param showSources - Whether to show sources for assistant messages
 */
const MessageBubbleComponent: React.FC<MessageBubbleProps> = ({ message, showSources = true }) => {
  const { role, content, sources, timestamp, modelUsed } = message;

  // Determine CSS class based on role
  const bubbleClass =
    role === 'user' ? styles.messageBubbleUser : styles.messageBubbleAssistant;

  // Determine if sources should be displayed
  const shouldShowSources = role === 'assistant' && showSources && sources && sources.length > 0;

  // Create ARIA label based on role
  const ariaLabel = role === 'user' ? 'Your message' : 'Assistant message';

  return (
    <div
      className={bubbleClass}
      role="article"
      aria-label={ariaLabel}
    >
      {/* Message content */}
      <div className={styles.messageContent} aria-labelledby={`message-content-${timestamp}`}>
        <p id={`message-content-${timestamp}`}>{content}</p>
      </div>

      {/* Sources (only for assistant messages with sources) */}
      {shouldShowSources && <SourcesDisplay sources={sources!} />}

      {/* Optional: timestamp */}
      {timestamp && (
        <div className={styles.messageTimestamp} aria-label="Message timestamp">
          {new Date(timestamp).toLocaleTimeString()}
        </div>
      )}

      {/* Optional: model used badge (for assistant messages) */}
      {role === 'assistant' && modelUsed && (
        <div className={styles.modelBadge} aria-label={`Model used: ${modelUsed}`}>
          Model: {modelUsed}
        </div>
      )}
    </div>
  );
};

// Memoize to prevent unnecessary re-renders
export const MessageBubble = React.memo(MessageBubbleComponent);

