/**
 * ChatInterface Component
 *
 * Main chat component that orchestrates message state management.
 * Phase 2: Integrated with GraphQL backend via generateClient.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '../../../../amplify/data/resource';
import { ChatInterfaceProps, ChatMessage, ErrorState } from '../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import styles from '../styles/ChatWithSources.module.css';

// Initialize GraphQL client at module level (reused across instances)
const client = generateClient<Schema>();

/**
 * ChatInterface Component
 *
 * Manages conversation state, message persistence, and orchestrates child components.
 * Integrated with GraphQL backend via generateClient<Schema>().
 *
 * @param conversationId - Unique conversation identifier
 * @param userId - User ID for authenticated mode (optional)
 * @param userToken - Auth token for authenticated mode (optional)
 * @param onSendMessage - Callback when message is sent
 * @param onResponseReceived - Callback when response is received
 * @param showSources - Whether to show sources for assistant messages
 * @param inputPlaceholder - Placeholder text for input
 */
export const ChatInterface: React.FC<ChatInterfaceProps> = ({
  conversationId,
  userId,
  userToken,
  onSendMessage,
  onResponseReceived,
  showSources = true,
  inputPlaceholder = 'Type your message...',
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);

  // SessionStorage key with conversationId
  const storageKey = `chat-${conversationId}`;

  // Restore messages from sessionStorage on mount
  useEffect(() => {
    const stored = sessionStorage.getItem(storageKey);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setMessages(parsed);
      } catch (e) {
        console.error('Failed to parse stored messages:', e);
      }
    }
  }, [storageKey]);

  // Save messages to sessionStorage when they change
  useEffect(() => {
    if (messages.length > 0) {
      sessionStorage.setItem(storageKey, JSON.stringify(messages));
    }
  }, [messages, storageKey]);

  // Handle send message (Phase 2: real GraphQL query)
  const handleSend = useCallback(
    async (messageText: string) => {
      // Create user message
      const userMessage: ChatMessage = {
        role: 'user',
        content: messageText,
        timestamp: new Date().toISOString(),
      };

      // Optimistic update: add user message immediately
      setMessages((prev) => [...prev, userMessage]);

      // Call onSendMessage callback if provided
      if (onSendMessage) {
        onSendMessage(messageText);
      }

      // Set loading state
      setIsLoading(true);
      setError(null);

      try {
        // Call GraphQL conversation query
        const response = await client.queries.conversation({
          message: messageText,
          conversationId: conversationId,
          userId: userId || undefined,
          userToken: userToken || undefined,
        });

        // Check for response data
        if (response.data) {
          const { content, sources, modelUsed } = response.data;

          // Create assistant message from response
          const assistantMessage: ChatMessage = {
            role: 'assistant',
            content: content || 'No response from assistant',
            timestamp: new Date().toISOString(),
            sources: sources || [],
            modelUsed: modelUsed || undefined,
          };

          // Add assistant message
          setMessages((prev) => [...prev, assistantMessage]);

          // Call onResponseReceived callback if provided
          if (onResponseReceived) {
            onResponseReceived(assistantMessage);
          }
        } else {
          // Handle case where response.data is null/undefined
          throw new Error(response.errors?.[0]?.message || 'No response data received');
        }
      } catch (err) {
        // Error classification and handling
        console.error('Conversation query error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';

        // Classify error type based on message patterns
        let errorType: ErrorState['type'] = 'unknown';
        let retryable = true;

        if (errorMessage.toLowerCase().includes('authentication required')) {
          errorType = 'auth';
          retryable = false;
        } else if (
          errorMessage.toLowerCase().includes('quota exceeded') ||
          errorMessage.toLowerCase().includes('quota')
        ) {
          errorType = 'quota';
          retryable = true;
        } else if (
          errorMessage.toLowerCase().includes('network') ||
          errorMessage.toLowerCase().includes('fetch')
        ) {
          errorType = 'network';
          retryable = true;
        } else if (errorMessage.toLowerCase().includes('validation')) {
          errorType = 'validation';
          retryable = false;
        }

        setError({
          type: errorType,
          message: errorMessage,
          retryable: retryable,
          onRetry: retryable
            ? () => {
                // Retry by re-sending the same message
                setError(null);
                handleSend(messageText);
              }
            : undefined,
        });
      } finally {
        setIsLoading(false);
      }
    },
    [conversationId, userId, userToken, onSendMessage, onResponseReceived]
  );

  return (
    <div className={styles.chatContainer}>
      <MessageList
        messages={messages}
        isLoading={isLoading}
        error={error}
        showSources={showSources}
      />
      <MessageInput onSend={handleSend} isLoading={isLoading} placeholder={inputPlaceholder} />
    </div>
  );
};

export default ChatInterface;
