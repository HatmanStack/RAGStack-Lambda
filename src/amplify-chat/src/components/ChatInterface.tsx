/**
 * ChatInterface Component
 *
 * Main chat component that orchestrates message state management.
 * Phase 1: Uses mock responses. Phase 2 will integrate with GraphQL backend.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ChatInterfaceProps, ChatMessage, ErrorState } from '../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import styles from '../styles/ChatWithSources.module.css';

/**
 * ChatInterface Component
 *
 * Manages conversation state, message persistence, and orchestrates child components.
 * Currently uses setTimeout to simulate backend responses (Phase 1).
 * GraphQL integration will replace mock logic in Phase 2.
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

  // Handle send message (Phase 1: mock response)
  const handleSend = useCallback(
    (messageText: string) => {
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

      // Simulate backend response with setTimeout (Phase 1)
      // Phase 2 will replace this with actual GraphQL query
      setTimeout(() => {
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: `This is a mock response to: "${messageText}". Real backend integration coming in Phase 2!`,
          timestamp: new Date().toISOString(),
          sources: [
            {
              title: 'Mock Document',
              location: 'Page 1',
              snippet: 'This is a mock source snippet for testing purposes.',
            },
          ],
          modelUsed: 'mock-model',
        };

        // Add assistant message
        setMessages((prev) => [...prev, assistantMessage]);
        setIsLoading(false);

        // Call onResponseReceived callback if provided
        if (onResponseReceived) {
          onResponseReceived(assistantMessage);
        }
      }, 1000); // 1 second delay to simulate network
    },
    [conversationId, onSendMessage, onResponseReceived]
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
