/**
 * ChatInterface Component Tests
 *
 * Tests the async mutation + polling flow for chat queries.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { ChatInterface } from '../ChatInterface';
import { mockScrollIntoView, mockSessionStorage, cleanupTestUtils } from '../../test-utils';

// Mock crypto.randomUUID
const MOCK_REQUEST_ID = 'mock-request-id-1234';
vi.stubGlobal('crypto', {
  randomUUID: vi.fn(() => MOCK_REQUEST_ID),
});

// Mock fetchCDNConfig and iamFetch
vi.mock('../../utils/fetchCDNConfig', () => ({
  fetchCDNConfig: vi.fn(() =>
    Promise.resolve({
      apiEndpoint: 'https://test-api.example.com/graphql',
      identityPoolId: 'us-east-1:test-identity-pool',
      region: 'us-east-1',
    })
  ),
}));

// Import the mocked module to configure it
import { iamFetch } from '../../utils/iamAuth';

vi.mock('../../utils/iamAuth', () => ({
  iamFetch: vi.fn(),
}));

const mockIamFetch = vi.mocked(iamFetch);

/**
 * Helper to create a mutation response (ChatRequest acknowledgment)
 */
function makeMutationResponse(conversationId = 'test-conv') {
  return {
    ok: true,
    json: async () => ({
      data: {
        queryKnowledgeBase: {
          conversationId,
          requestId: MOCK_REQUEST_ID,
          status: 'PENDING',
        },
      },
    }),
  } as Response;
}

/**
 * Helper to create a poll response with a specific status
 */
function makePollResponse(
  status: 'PENDING' | 'COMPLETED' | 'ERROR',
  options: {
    conversationId?: string;
    assistantResponse?: string;
    error?: string;
    sources?: Array<{ documentId: string; s3Uri: string; snippet?: string; pageNumber?: number }>;
  } = {}
) {
  const {
    conversationId = 'test-conv',
    assistantResponse = 'Mock assistant response',
    error: errorMsg,
    sources = [],
  } = options;

  return {
    ok: true,
    json: async () => ({
      data: {
        getConversation: {
          conversationId,
          turns: [
            {
              turnNumber: 1,
              requestId: MOCK_REQUEST_ID,
              status,
              userMessage: 'Test message',
              assistantResponse: status === 'COMPLETED' ? assistantResponse : null,
              sources: status === 'COMPLETED' ? sources : [],
              error: status === 'ERROR' ? (errorMsg || 'Processing error') : null,
              createdAt: '2024-01-01T12:00:00Z',
            },
          ],
        },
      },
    }),
  } as Response;
}

/**
 * Helper to determine if a fetch call is a mutation or poll based on request body
 */
function isMutationCall(body: string): boolean {
  return body.includes('mutation QueryKnowledgeBase');
}

describe('ChatInterface', () => {
  beforeEach(() => {
    mockScrollIntoView();
    mockSessionStorage();
    mockIamFetch.mockReset();
  });

  afterEach(() => {
    cleanupTestUtils();
    vi.restoreAllMocks();
  });

  it('renders MessageList and MessageInput components', () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('adds user message when handleSend is called', async () => {
    // Mock: mutation succeeds, first poll returns COMPLETED
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('COMPLETED');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    // User message should appear immediately
    expect(screen.getByText('Hello')).toBeInTheDocument();

    await waitFor(() => {
      expect(mockIamFetch).toHaveBeenCalled();
    });
  });

  it('sets isLoading to true during mutation and polling', async () => {
    // Mock: mutation succeeds, first poll returns COMPLETED
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('COMPLETED');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    // Loading indicator should appear
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();

    // Wait for response to complete
    await waitFor(() => {
      expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();
    });
  });

  it('sends mutation then polls and displays response (happy path)', async () => {
    let pollCount = 0;

    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      // First poll: PENDING, second poll: COMPLETED
      pollCount++;
      if (pollCount === 1) return makePollResponse('PENDING');
      return makePollResponse('COMPLETED', {
        assistantResponse: 'The answer is 42',
        sources: [
          {
            documentId: 'test-doc.pdf',
            pageNumber: 1,
            s3Uri: 's3://test/doc.pdf',
            snippet: 'Test snippet',
          },
        ],
      });
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'What is the answer?' } });
    fireEvent.click(sendButton);

    // Wait for assistant response to appear
    await waitFor(
      () => {
        expect(screen.getByText('The answer is 42')).toBeInTheDocument();
      },
      { timeout: 10000 }
    );

    // Loading should be gone
    expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();

    // Mutation was called once, polls were called at least twice
    const mutationCalls = mockIamFetch.mock.calls.filter(([, body]) => isMutationCall(body));
    expect(mutationCalls).toHaveLength(1);
    expect(pollCount).toBeGreaterThanOrEqual(2);
  });

  it('shows error when poll returns ERROR status', async () => {
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('ERROR', { error: 'Knowledge base unavailable' });
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Test question' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText('Knowledge base unavailable')).toBeInTheDocument();
    });
  });

  it('shows error when mutation HTTP request fails', async () => {
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) {
        return {
          ok: false,
          status: 500,
          statusText: 'Internal Server Error',
        } as Response;
      }
      return makePollResponse('COMPLETED');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Test question' } });
    fireEvent.click(sendButton);

    await waitFor(() => {
      expect(screen.getByText(/HTTP 500/i)).toBeInTheDocument();
    });
  });

  it('disables input during mutation + polling flow', async () => {
    let resolveFirstPoll: (() => void) | undefined;

    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      // First poll blocks until we resolve it
      if (!resolveFirstPoll) {
        await new Promise<void>((resolve) => {
          resolveFirstPoll = () => {
            resolve();
          };
        });
      }
      return makePollResponse('COMPLETED');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Test question' } });
    fireEvent.click(sendButton);

    // Input should be disabled during loading
    await waitFor(() => {
      expect(input).toBeDisabled();
    });

    // Resolve the poll
    await act(async () => {
      resolveFirstPoll?.();
    });

    // Wait for loading to finish
    await waitFor(() => {
      expect(input).not.toBeDisabled();
    });
  });

  it('calls onSendMessage callback when message is sent', async () => {
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('COMPLETED');
    });

    const mockOnSendMessage = vi.fn();
    render(
      <ChatInterface conversationId="test-1" onSendMessage={mockOnSendMessage} showSources={true} />
    );

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Callback test' } });
    fireEvent.click(sendButton);

    expect(mockOnSendMessage).toHaveBeenCalledWith('Callback test', 'test-1');

    await waitFor(() => {
      expect(mockIamFetch).toHaveBeenCalled();
    });
  });

  it('calls onResponseReceived callback when response is received', async () => {
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('COMPLETED', {
        assistantResponse: 'Response received',
      });
    });

    const mockOnResponseReceived = vi.fn();
    render(
      <ChatInterface
        conversationId="test-1"
        onResponseReceived={mockOnResponseReceived}
        showSources={true}
      />
    );

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Response test' } });
    fireEvent.click(sendButton);

    await waitFor(
      () => {
        expect(mockOnResponseReceived).toHaveBeenCalledOnce();
      },
      { timeout: 5000 }
    );

    const receivedMessage = mockOnResponseReceived.mock.calls[0][0];
    expect(receivedMessage.role).toBe('assistant');
    expect(receivedMessage.content).toBe('Response received');
  });

  it('shows timeout error after 90s of polling', async () => {
    // Mock Date.now to simulate time passing beyond 90s
    const startTime = Date.now();
    let dateNowCallCount = 0;

    vi.spyOn(Date, 'now').mockImplementation(() => {
      dateNowCallCount++;
      // First call sets startTime in pollForResult, keep it at real time.
      // Subsequent calls simulate 91s elapsed to trigger timeout.
      if (dateNowCallCount <= 1) return startTime;
      return startTime + 91000;
    });

    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      return makePollResponse('PENDING');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Timeout test' } });
    fireEvent.click(sendButton);

    // The timeout check happens before the first poll request even fires,
    // since Date.now() returns 91s after startTime on the second call.
    // The error shows up quickly because the timeout triggers on the first loop iteration.
    await waitFor(
      () => {
        expect(screen.getByText(/timed out/i)).toBeInTheDocument();
      },
      { timeout: 10000 }
    );

    vi.mocked(Date.now).mockRestore();
  });

  it('shows slow response indicator after 30s threshold', async () => {
    // Mock Date.now: first call returns start, subsequent calls return 31s later
    const startTime = Date.now();
    let dateNowCallCount = 0;

    vi.spyOn(Date, 'now').mockImplementation(() => {
      dateNowCallCount++;
      if (dateNowCallCount <= 1) return startTime;
      return startTime + 31000;
    });

    let pollCount = 0;
    mockIamFetch.mockImplementation(async (_url, body) => {
      if (isMutationCall(body)) return makeMutationResponse();
      pollCount++;
      // After slow threshold fires, return COMPLETED to end the test
      if (pollCount > 1) return makePollResponse('COMPLETED');
      return makePollResponse('PENDING');
    });

    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(input, { target: { value: 'Slow test' } });
    fireEvent.click(sendButton);

    // The slow response message should appear after Date.now reports > 30s
    // The onSlowThreshold callback fires during the polling loop,
    // but React may not re-render immediately. Wait with longer timeout
    // to account for the 2s real setTimeout delay in polling.
    await waitFor(
      () => {
        expect(screen.getByText('Taking longer than usual...')).toBeInTheDocument();
      },
      { timeout: 10000 }
    );

    vi.mocked(Date.now).mockRestore();
  });
});
