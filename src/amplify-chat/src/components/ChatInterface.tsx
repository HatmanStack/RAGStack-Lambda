/**
 * ChatInterface Component
 *
 * Main chat component that orchestrates message state management.
 * Phase 2: Integrated with GraphQL backend via generateClient.
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { generateClient } from 'aws-amplify/api';
import { ChatInterfaceProps, ChatMessage, ErrorState } from '../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import styles from '../styles/ChatWithSources.module.css';

// GraphQL query for conversation
const CONVERSATION_QUERY = `
  query Conversation($message: String!, $conversationId: String!, $userId: String, $userToken: String) {
    conversation(message: $message, conversationId: $conversationId, userId: $userId, userToken: $userToken) {
      content
      sources {
        title
        location
        snippet
        documentUrl
        documentAccessAllowed
      }
      modelUsed
    }
  }
`;

// Initialize GraphQL client at module level (reused across instances)
const client = generateClient();

// Message limit to prevent sessionStorage quota exceeded (module scope constant)
const MESSAGE_LIMIT = 50;

// Maximum retry attempts before marking error as non-retryable
const MAX_RETRIES = 3;

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

  // Determine authentication mode
  const isAuthenticated = Boolean(userId && userToken);
  const hasPartialCredentials = Boolean(userId && !userToken) || Boolean(!userId && userToken);

  // Warn about partial credentials
  useEffect(() => {
    if (hasPartialCredentials) {
      console.warn(
        'ChatInterface: Both userId and userToken must be provided for authenticated mode. ' +
          'Currently in invalid state - messages may fail.'
      );
    }
  }, [hasPartialCredentials]);

  // SessionStorage key with userId and conversationId for isolation
  const storageKey = `chat-${userId || 'guest'}-${conversationId}`;

  // Restore messages from sessionStorage on mount (clear first to handle storageKey changes)
  useEffect(() => {
    // Clear messages first - prevents old messages from persisting when storageKey changes
    setMessages([]);

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

  // Save messages to sessionStorage when they change (with message limit and error handling)
  useEffect(() => {
    if (messages.length > 0) {
      try {
        // Limit stored messages to prevent quota exceeded
        const messagesToStore =
          messages.length > MESSAGE_LIMIT ? messages.slice(-MESSAGE_LIMIT) : messages;

        sessionStorage.setItem(storageKey, JSON.stringify(messagesToStore));
      } catch (err) {
        // Handle QuotaExceededError gracefully
        if (err instanceof DOMException && err.name === 'QuotaExceededError') {
          console.warn(
            `ChatInterface: sessionStorage quota exceeded for key "${storageKey}". ` +
              'Conversation will continue without persistence.'
          );
        } else {
          console.error('ChatInterface: Failed to save messages to sessionStorage:', err);
        }
      }
    }
  }, [messages, storageKey]);

  // Clear conversation from sessionStorage and component state
  const clearConversation = useCallback(() => {
    try {
      sessionStorage.removeItem(storageKey);
      setMessages([]);
      setError(null);
      console.log(`ChatInterface: Cleared conversation "${storageKey}"`);
    } catch (err) {
      console.error('ChatInterface: Failed to clear conversation:', err);
    }
  }, [storageKey]);

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
        onSendMessage(messageText, conversationId);
      }

      // Set loading state
      setIsLoading(true);
      setError(null);

      try {
        // Debug logging for authentication
        console.log('[ChatInterface] Sending conversation query', {
          conversationId,
          isAuthenticated,
          hasUserId: !!userId,
          hasUserToken: !!userToken,
        });

        // Call GraphQL conversation query
        // Type assertion needed because generateClient returns a union type that includes
        // subscription results, but we're using a query which always returns GraphQLResult
        const response = await client.graphql({
          query: CONVERSATION_QUERY,
          variables: {
            message: messageText,
            conversationId: conversationId,
            userId: userId || undefined,
            userToken: userToken || undefined,
          },
        }) as { data?: { conversation?: { content: string; sources?: Array<{ title: string; location: string; snippet: string; documentUrl?: string; documentAccessAllowed?: boolean }>; modelUsed?: string } }; errors?: Array<{ message: string }> };

        console.log('[ChatInterface] Query successful', {
          hasData: !!response.data,
          hasConversation: !!response.data?.conversation,
        });

        // Check for response data
        if (response.data?.conversation) {
          const { content, sources, modelUsed } = response.data.conversation;

          // Debug: Log full conversation response
          console.log('[ChatInterface] Full conversation response:', response.data.conversation);
          console.log('[ChatInterface] Sources received:', sources?.map((s: { title: string; documentUrl?: string; documentAccessAllowed?: boolean }) => ({
            title: s.title,
            hasDocumentUrl: !!s.documentUrl,
            documentUrl: s.documentUrl?.substring(0, 50) + '...',
            documentAccessAllowed: s.documentAccessAllowed
          })));

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
        console.error('[ChatInterface] Conversation query error:', err);
        console.error('[ChatInterface] Error details:', JSON.stringify(err, null, 2));
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

        // Get current retry count from error state
        const currentRetryCount = error?.retryCount || 0;
        const canRetry = retryable && currentRetryCount < MAX_RETRIES;

        setError({
          type: errorType,
          message: errorMessage,
          retryable: canRetry,
          retryCount: currentRetryCount,
          onRetry: canRetry
            ? () => {
                // Increment retry count and retry by re-sending the same message
                setError((prevError) => ({
                  ...prevError!,
                  retryCount: (prevError?.retryCount || 0) + 1,
                }));
                handleSend(messageText);
              }
            : undefined,
        });
      } finally {
        setIsLoading(false);
      }
    },
    // Note: onSendMessage and onResponseReceived are intentionally excluded from deps
    // to prevent handleSend recreation when parent passes new callback references.
    // These are optional side-effect callbacks that don't affect core functionality.
    [conversationId, userId, userToken]
  );

  return (
    <div className={styles.chatContainer}>
      {/* Authentication status indicator */}
      {(isAuthenticated || hasPartialCredentials) && (
        <div className={styles.authStatus}>
          {isAuthenticated && (
            <span className={styles.authBadge} title={`Authenticated as: ${userId}`}>
              🔐 Authenticated
            </span>
          )}
          {hasPartialCredentials && (
            <span className={styles.authWarning} title="Incomplete credentials">
              ⚠️ Invalid Auth
            </span>
          )}
        </div>
      )}
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
