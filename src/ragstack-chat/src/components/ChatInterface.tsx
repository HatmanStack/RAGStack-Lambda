/**
 * ChatInterface Component
 *
 * Main chat component that orchestrates message state management.
 * Uses IAM authentication via Cognito Identity Pool for AppSync API calls.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { ChatInterfaceProps, ChatMessage, ErrorState } from '../types';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { fetchCDNConfig } from '../utils/fetchCDNConfig';
import { iamFetch } from '../utils/iamAuth';
import styles from '../styles/ChatWithSources.module.css';

/** Generate a UUID v4 using crypto API */
function generateRequestId(): string {
  return crypto.randomUUID();
}

// GraphQL mutation for async chat query
const QUERY_KB_MUTATION = `
  mutation QueryKnowledgeBase($query: String!, $conversationId: ID!, $requestId: ID!) {
    queryKnowledgeBase(query: $query, conversationId: $conversationId, requestId: $requestId) {
      conversationId
      requestId
      status
    }
  }
`;

// GraphQL query for polling conversation results
const GET_CONVERSATION_QUERY = `
  query GetConversation($conversationId: ID!) {
    getConversation(conversationId: $conversationId) {
      conversationId
      turns {
        turnNumber
        requestId
        status
        userMessage
        assistantResponse
        sources {
          documentId
          pageNumber
          s3Uri
          snippet
          documentUrl
          documentAccessAllowed
          score
          filename
          isMedia
          isSegment
          segmentUrl
          mediaType
          contentType
          timestampStart
          timestampEnd
          timestampDisplay
          speaker
          isImage
          isScraped
          sourceUrl
        }
        error
        createdAt
      }
    }
  }
`;

// Polling configuration
const POLL_INTERVAL_INITIAL_MS = 1000;  // Start polling at 1s
const POLL_INTERVAL_MAX_MS = 5000;      // Cap at 5s
const SLOW_THRESHOLD_MS = 30000;        // "Still working" after 30s
const HARD_TIMEOUT_MS = 90000;          // Hard timeout at 90s
const MAX_CONSECUTIVE_POLL_FAILURES = 5; // Surface error after N consecutive poll failures

// Message limit to prevent sessionStorage quota exceeded (module scope constant)
const MESSAGE_LIMIT = 50;

// Maximum retry attempts before marking error as non-retryable
const MAX_RETRIES = 3;

/**
 * Send async chat mutation
 */
async function sendChatMutation(
  message: string,
  conversationId: string,
  requestId: string,
): Promise<{ conversationId: string; requestId: string; status: string }> {
  const config = await fetchCDNConfig();
  if (!config?.apiEndpoint || !config?.identityPoolId || !config?.region) {
    throw new Error('API endpoint not available. Please check your configuration.');
  }

  const body = JSON.stringify({
    query: QUERY_KB_MUTATION,
    variables: { query: message, conversationId, requestId },
  });

  const response = await iamFetch(config.apiEndpoint, body, config.identityPoolId, config.region);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const result = await response.json();
  if (result.errors?.length > 0) {
    throw new Error(result.errors[0].message);
  }

  if (!result.data?.queryKnowledgeBase) {
    throw new Error('No response data received');
  }

  return result.data.queryKnowledgeBase;
}

/**
 * Poll getConversation for a specific requestId's result
 */
async function pollForResult(
  conversationId: string,
  requestId: string,
  onSlowThreshold: () => void,
  signal?: AbortSignal,
): Promise<{
  answer: string;
  sources: Array<{
    documentId: string;
    pageNumber?: number;
    s3Uri: string;
    snippet?: string;
    documentUrl?: string;
    documentAccessAllowed?: boolean;
    score?: number;
    filename?: string;
    isMedia?: boolean;
    isSegment?: boolean;
    segmentUrl?: string;
    mediaType?: string;
    contentType?: string;
    timestampStart?: number;
    timestampEnd?: number;
    timestampDisplay?: string;
    speaker?: string;
    isImage?: boolean;
    isScraped?: boolean;
    sourceUrl?: string;
  }>;
  error?: string;
}> {
  const config = await fetchCDNConfig();
  if (!config?.apiEndpoint || !config?.identityPoolId || !config?.region) {
    throw new Error('API endpoint not available.');
  }

  const startTime = Date.now();
  let slowNotified = false;
  let consecutiveFailures = 0;
  let pollInterval = POLL_INTERVAL_INITIAL_MS;

  // eslint-disable-next-line no-constant-condition
  while (true) {
    if (signal?.aborted) {
      throw new DOMException('Polling aborted', 'AbortError');
    }

    const elapsed = Date.now() - startTime;

    // Hard timeout
    if (elapsed > HARD_TIMEOUT_MS) {
      throw new Error('Response timed out. The query may still be processing. Please try again.');
    }

    // Slow threshold notification
    if (!slowNotified && elapsed > SLOW_THRESHOLD_MS) {
      slowNotified = true;
      onSlowThreshold();
    }

    // Poll
    const body = JSON.stringify({
      query: GET_CONVERSATION_QUERY,
      variables: { conversationId },
    });

    const response = await iamFetch(
      config.apiEndpoint, body, config.identityPoolId, config.region, signal
    );
    if (response.ok) {
      consecutiveFailures = 0;
      const result = await response.json();
      const conversation = result.data?.getConversation;

      if (conversation?.turns) {
        // Find the turn matching our requestId
        const matchingTurn = conversation.turns.find(
          (t: { requestId?: string }) => t.requestId === requestId
        );

        if (matchingTurn) {
          if (matchingTurn.status === 'COMPLETED') {
            return {
              answer: matchingTurn.assistantResponse || '',
              sources: matchingTurn.sources || [],
            };
          }

          if (matchingTurn.status === 'ERROR') {
            throw new Error(matchingTurn.error || 'An error occurred processing your query.');
          }

          // PENDING - continue polling
        }
      }
    } else {
      consecutiveFailures++;
      // Surface persistent non-transient errors (4xx) immediately
      if (response.status >= 400 && response.status < 500) {
        throw new Error(`Server error (HTTP ${response.status}). Please try again.`);
      }
      if (consecutiveFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
        throw new Error(`Unable to reach server after ${consecutiveFailures} attempts. Please try again.`);
      }
    }

    // Wait with step backoff before next poll
    await new Promise((resolve) => setTimeout(resolve, pollInterval));
    pollInterval = Math.min(pollInterval * 1.5, POLL_INTERVAL_MAX_MS);
  }
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
  userToken: _userToken,
  onSendMessage,
  onResponseReceived,
  showSources = true,
  inputPlaceholder = 'Type your message...',
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSlowResponse, setIsSlowResponse] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);

  // Use ref to track retry count to avoid stale closure issues in handleSend
  const retryCountRef = useRef(0);

  // AbortController ref to cancel in-flight polling on unmount or new send
  const abortControllerRef = useRef<AbortController | null>(null);

  // Stable refs for optional callbacks to avoid stale closures without triggering re-renders
  const onSendMessageRef = useRef(onSendMessage);
  const onResponseReceivedRef = useRef(onResponseReceived);
  onSendMessageRef.current = onSendMessage;
  onResponseReceivedRef.current = onResponseReceived;

  // Abort polling on unmount
  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

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
      } catch {
        // QuotaExceededError or other storage errors - conversation continues without persistence
      }
    }
  }, [messages, storageKey]);

  // Handle send message
  const handleSend = useCallback(
    async (messageText: string, isRetry = false) => {
      // Only add user message on first attempt, not retries
      if (!isRetry) {
        const userMessage: ChatMessage = {
          role: 'user',
          content: messageText,
          timestamp: new Date().toISOString(),
        };

        // Optimistic update: add user message immediately
        setMessages((prev) => [...prev, userMessage]);
      }

      // Call onSendMessage callback if provided
      if (onSendMessageRef.current) {
        onSendMessageRef.current(messageText, conversationId);
      }

      // Set loading state
      setIsLoading(true);
      setError(null);
      setIsSlowResponse(false);

      // Abort any in-flight polling from a previous send
      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        // Generate a unique requestId for this message
        const requestId = generateRequestId();

        // Send async mutation
        await sendChatMutation(messageText, conversationId, requestId);

        // Poll for result
        const response = await pollForResult(
          conversationId,
          requestId,
          () => setIsSlowResponse(true),
          controller.signal,
        );

        // Map sources to the format expected by the UI
        const mappedSources = (response.sources || []).map((s) => ({
          title: s.documentId || s.filename || 'Unknown',
          location: s.pageNumber ? `Page ${s.pageNumber}` : '',
          snippet: s.snippet || '',
          documentUrl: s.documentUrl,
          documentAccessAllowed: s.documentAccessAllowed,
          score: s.score,
          documentId: s.documentId,
          filename: s.filename,
          isMedia: s.isMedia,
          isSegment: s.isSegment,
          segmentUrl: s.segmentUrl,
          mediaType: s.mediaType as 'video' | 'audio' | undefined,
          contentType: s.contentType as 'transcript' | 'visual' | undefined,
          timestampStart: s.timestampStart,
          timestampEnd: s.timestampEnd,
          timestampDisplay: s.timestampDisplay,
          speaker: s.speaker,
          isImage: s.isImage,
          isScraped: s.isScraped,
          sourceUrl: s.sourceUrl,
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

        // Reset retry count on successful response
        retryCountRef.current = 0;

        // Call onResponseReceived callback if provided
        if (onResponseReceivedRef.current) {
          onResponseReceivedRef.current(assistantMessage);
        }
      } catch (err) {
        // Silently ignore aborted requests (unmount or new send replacing old one)
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }

        // Error classification and handling
        console.error('[RagStackChat] Query error:', err);
        const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';

        // Classify error type based on message patterns
        let errorType: ErrorState['type'] = 'unknown';
        let retryable = true;

        if (errorMessage.toLowerCase().includes('authentication required')) {
          errorType = 'auth';
          retryable = false;
        } else if (errorMessage.toLowerCase().includes('demo mode')) {
          // Demo mode quota errors are not retryable (resets next day)
          errorType = 'quota';
          retryable = false;
        } else if (
          errorMessage.toLowerCase().includes('quota exceeded') ||
          errorMessage.toLowerCase().includes('quota')
        ) {
          errorType = 'quota';
          retryable = true;
        } else if (errorMessage.toLowerCase().includes('timed out')) {
          errorType = 'network';
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

        // Get current retry count from ref (avoids stale closure issues)
        const currentRetryCount = retryCountRef.current;
        const canRetry = retryable && currentRetryCount < MAX_RETRIES;

        setError({
          type: errorType,
          message: errorMessage,
          retryable: canRetry,
          retryCount: currentRetryCount,
          onRetry: canRetry
            ? () => {
                // Increment retry count via ref and retry (isRetry=true to avoid duplicate message)
                retryCountRef.current += 1;
                handleSend(messageText, true);
              }
            : undefined,
        });
      } finally {
        setIsLoading(false);
        setIsSlowResponse(false);
      }
    },
    // Callbacks accessed via refs (onSendMessageRef, onResponseReceivedRef) — always current.
    // retryCountRef is a ref and doesn't need to be in deps.
    [conversationId]
  );

  // Reset retry count on conversation change only
  // (not on messages.length - that would reset during retry flow)
  useEffect(() => {
    retryCountRef.current = 0;
  }, [conversationId]);

  return (
    <div className={styles.chatContainer}>
      <MessageList
        messages={messages}
        isLoading={isLoading}
        isSlowResponse={isSlowResponse}
        error={error}
        showSources={showSources}
      />
      <MessageInput onSend={handleSend} isLoading={isLoading} placeholder={inputPlaceholder} />
    </div>
  );
};

