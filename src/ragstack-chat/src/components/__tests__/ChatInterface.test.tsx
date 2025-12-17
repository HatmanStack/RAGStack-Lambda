/**
 * ChatInterface Component Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChatInterface } from '../ChatInterface';
import { mockScrollIntoView, mockSessionStorage, cleanupTestUtils } from '../../test-utils';

// Mock fetch globally
const mockFetch = vi.fn();

describe('ChatInterface', () => {
  beforeEach(() => {
    // Mock browser APIs
    mockScrollIntoView();
    mockSessionStorage();

    // Set up global SAM_GRAPHQL_ENDPOINT
    (globalThis as unknown as { SAM_GRAPHQL_ENDPOINT: string }).SAM_GRAPHQL_ENDPOINT =
      'https://test-api.example.com/graphql';
    (globalThis as unknown as { SAM_GRAPHQL_API_KEY: string }).SAM_GRAPHQL_API_KEY = 'test-api-key';

    // Reset and configure the fetch mock
    mockFetch.mockReset();
    globalThis.fetch = mockFetch;

    // Default mock response
    mockFetch.mockImplementation(async (_url, options) => {
      const body = JSON.parse(options?.body || '{}');
      const query = body.variables?.query || 'unknown';
      return {
        ok: true,
        json: async () => ({
          data: {
            queryKnowledgeBase: {
              answer: `Mock response to: ${query}`,
              conversationId: body.variables?.conversationId || 'test-conv',
              sources: [
                {
                  documentId: 'test-doc.pdf',
                  pageNumber: 1,
                  s3Uri: 's3://test/doc.pdf',
                  snippet: 'Test snippet from document',
                },
              ],
            },
          },
        }),
      };
    });
  });

  afterEach(() => {
    cleanupTestUtils();
    vi.restoreAllMocks();
    // Clean up global variables
    delete (globalThis as unknown as { SAM_GRAPHQL_ENDPOINT?: string }).SAM_GRAPHQL_ENDPOINT;
    delete (globalThis as unknown as { SAM_GRAPHQL_API_KEY?: string }).SAM_GRAPHQL_API_KEY;
  });

  it('renders MessageList and MessageInput components', () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    // Should show empty state initially
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument();

    // Input should be present
    expect(screen.getByPlaceholderText(/type your message/i)).toBeInTheDocument();

    // Send button should be present
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('adds user message when handleSend is called', async () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    // User message should appear immediately
    expect(screen.getByText('Hello')).toBeInTheDocument();

    // Wait for async fetch call to complete to avoid act() warnings
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('sets isLoading to true during mock response', async () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    // Loading indicator should appear
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();

    // Wait for async response to complete
    await waitFor(() => {
      expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();
    });
  });

  it('adds assistant message after delay', async () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Test question' } });
    fireEvent.click(sendButton);

    // Wait for assistant message to appear (using real timers with 1s delay)
    await waitFor(
      () => {
        expect(screen.getByText(/mock response to/i)).toBeInTheDocument();
      },
      { timeout: 2000 }
    );

    // Loading indicator should be gone
    expect(screen.queryByText('Assistant is typing')).not.toBeInTheDocument();
  });

  it.skip('persists messages to sessionStorage', async () => {
    // TODO: Fix sessionStorage mock - currently not capturing writes correctly
    render(<ChatInterface conversationId="test-persist" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Persist this' } });
    fireEvent.click(sendButton);

    // First verify the message appears in the UI (confirms state update)
    expect(await screen.findByText('Persist this')).toBeInTheDocument();

    // Then check sessionStorage was written (useEffect runs after state update)
    await waitFor(() => {
      const stored = sessionStorage.getItem('chat-test-persist');
      expect(stored).not.toBeNull();
    });

    const stored = sessionStorage.getItem('chat-test-persist');
    const parsed = JSON.parse(stored!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].content).toBe('Persist this');
  });

  it.skip('restores messages from sessionStorage on mount', async () => {
    // TODO: Fix sessionStorage mock - currently not restoring correctly
    // Pre-populate sessionStorage BEFORE rendering the component
    const existingMessages = [
      {
        role: 'user',
        content: 'Previous message',
        timestamp: '2024-01-01T12:00:00Z',
      },
    ];
    sessionStorage.setItem('chat-test-restore', JSON.stringify(existingMessages));

    // Verify sessionStorage has the data before rendering
    expect(sessionStorage.getItem('chat-test-restore')).not.toBeNull();

    render(<ChatInterface conversationId="test-restore" showSources={true} />);

    // Wait for the message to appear (useEffect restoration is async)
    expect(await screen.findByText('Previous message')).toBeInTheDocument();
  });

  it('calls onSendMessage callback when message is sent', async () => {
    const mockOnSendMessage = vi.fn();
    render(
      <ChatInterface conversationId="test-1" onSendMessage={mockOnSendMessage} showSources={true} />
    );

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Callback test' } });
    fireEvent.click(sendButton);

    // Callback should be called with message text and conversation ID
    expect(mockOnSendMessage).toHaveBeenCalledWith('Callback test', 'test-1');

    // Wait for async operations to complete
    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalled();
    });
  });

  it('calls onResponseReceived callback when response is received', async () => {
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

    // Send a message
    fireEvent.change(input, { target: { value: 'Response test' } });
    fireEvent.click(sendButton);

    // Wait for callback to be called (using real timers with 1s delay)
    await waitFor(
      () => {
        expect(mockOnResponseReceived).toHaveBeenCalledOnce();
      },
      { timeout: 2000 }
    );

    // Check that callback received the assistant message
    const receivedMessage = mockOnResponseReceived.mock.calls[0][0];
    expect(receivedMessage.role).toBe('assistant');
    expect(receivedMessage.content).toContain('Mock response');
  });
});
