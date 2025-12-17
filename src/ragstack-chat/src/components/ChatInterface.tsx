/**
 * ChatInterface Component
 *
 * Main chat component that orchestrates message state management.
 * Uses direct fetch to SAM AppSync API.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { ChatInterfaceProps, ChatMessage, ErrorState } from '../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import styles from '../styles/ChatWithSources.module.css';

// GraphQL query for SAM AppSync queryKnowledgeBase
const QUERY_KB_QUERY = `
  query QueryKnowledgeBase($query: String!, $conversationId: String) {
    queryKnowledgeBase(query: $query, conversationId: $conversationId) {
      answer
      conversationId
      sources {
        documentId
        pageNumber
        s3Uri
        snippet
        documentUrl
        documentAccessAllowed
      }
      error
    }
  }
`;

// Get SAM API endpoint and key from build-time config
// These are injected by the inject-amplify-config.js script
declare const SAM_GRAPHQL_ENDPOINT: string | undefined;
declare const SAM_GRAPHQL_API_KEY: string | undefined;

// Message limit to prevent sessionStorage quota exceeded (module scope constant)
const MESSAGE_LIMIT = 50;

// Maximum retry attempts before marking error as non-retryable
const MAX_RETRIES = 3;

/**
 * Query SAM AppSync API directly using fetch
 */
async function queryKnowledgeBase(
  message: string,
  conversationId: string
): Promise<{
  answer: string;
  conversationId: string | null;
  sources: Array<{
    documentId: string;
    pageNumber?: number;
    s3Uri: string;
    snippet?: string;
    documentUrl?: string;
    documentAccessAllowed?: boolean;
  }>;
  error?: string;
}> {
  const endpoint = typeof SAM_GRAPHQL_ENDPOINT !== 'undefined' ? SAM_GRAPHQL_ENDPOINT : '';
  const apiKey = typeof SAM_GRAPHQL_API_KEY !== 'undefined' ? SAM_GRAPHQL_API_KEY : '';

  if (!endpoint) {
    throw new Error('SAM_GRAPHQL_ENDPOINT not configured. Check web component build configuration.');
  }

  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'x-api-key': apiKey } : {}),
    },
    body: JSON.stringify({
      query: QUERY_KB_QUERY,
      variables: {
        query: message,
        conversationId: conversationId,
      },
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const result = await response.json();

  if (result.errors && result.errors.length > 0) {
    throw new Error(result.errors[0].message);
  }

  if (!result.data?.queryKnowledgeBase) {
    throw new Error('No response data received');
  }

  const kbResponse = result.data.queryKnowledgeBase;

  if (kbResponse.error) {
    throw new Error(kbResponse.error);
  }

  return kbResponse;
}

/**
 * ChatInterface Component
 *
 * Manages conversation state, message persistence, and orchestrates child components.
 * Uses direct fetch to SAM AppSync API.
 *
 * @param conversationId - Unique conversation identifier
 * @param userId - User ID for authenticated mode (optional, for future use)
 * @param userToken - Auth token for authenticated mode (optional, for future use)
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

  // Handle send message
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
        console.log('[RagStackChat] Sending query to SAM API', {
          conversationId,
          messageLength: messageText.length,
        });

        // Call SAM AppSync API directly
        const response = await queryKnowledgeBase(messageText, conversationId);

        console.log('[RagStackChat] Query successful', {
          hasAnswer: !!response.answer,
          sourcesCount: response.sources?.length || 0,
        });

        // Map sources to the format expected by the UI
        const mappedSources = (response.sources || []).map((s) => ({
          title: s.documentId,
          location: s.pageNumber ? `Page ${s.pageNumber}` : '',
          snippet: s.snippet || '',
          documentUrl: s.documentUrl,
          documentAccessAllowed: s.documentAccessAllowed,
        }));

        // Create assistant message from response
        const assistantMessage: ChatMessage = {
          role: 'assistant',
          content: response.answer || 'No response from assistant',
          timestamp: new Date().toISOString(),
          sources: mappedSources,
        };

        // Add assistant message
        setMessages((prev) => [...prev, assistantMessage]);

        // Call onResponseReceived callback if provided
        if (onResponseReceived) {
          onResponseReceived(assistantMessage);
        }
      } catch (err) {
        // Error classification and handling
        console.error('[RagStackChat] Query error:', err);
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
          errorMessage.toLowerCase().includes('fetch') ||
          errorMessage.toLowerCase().includes('http')
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
    [conversationId, error]
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
