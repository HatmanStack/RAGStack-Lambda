/**
 * ChatInterface Component Tests
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ChatInterface } from '../ChatInterface';
import { mockScrollIntoView, mockSessionStorage, cleanupTestUtils } from '../../test-utils';

describe('ChatInterface', () => {
  beforeEach(() => {
    // Mock browser APIs
    mockScrollIntoView();
    mockSessionStorage();
  });

  afterEach(() => {
    cleanupTestUtils();
    vi.restoreAllMocks();
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

  it('adds user message when handleSend is called', () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);

    // User message should appear immediately
    expect(screen.getByText('Hello')).toBeInTheDocument();
  });

  it('sets isLoading to true during mock response', () => {
    render(<ChatInterface conversationId="test-1" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    // Loading indicator should appear
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
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

  it('persists messages to sessionStorage', () => {
    render(<ChatInterface conversationId="test-persist" showSources={true} />);

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Persist this' } });
    fireEvent.click(sendButton);

    // Check sessionStorage
    const stored = sessionStorage.getItem('chat-test-persist');
    expect(stored).toBeTruthy();

    const parsed = JSON.parse(stored!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].content).toBe('Persist this');
  });

  it('restores messages from sessionStorage on mount', () => {
    // Pre-populate sessionStorage
    const existingMessages = [
      {
        role: 'user',
        content: 'Previous message',
        timestamp: '2024-01-01T12:00:00Z',
      },
    ];
    sessionStorage.setItem('chat-test-restore', JSON.stringify(existingMessages));

    render(<ChatInterface conversationId="test-restore" showSources={true} />);

    // Previous message should be displayed
    expect(screen.getByText('Previous message')).toBeInTheDocument();
  });

  it('calls onSendMessage callback when message is sent', () => {
    const mockOnSendMessage = vi.fn();
    render(
      <ChatInterface conversationId="test-1" onSendMessage={mockOnSendMessage} showSources={true} />
    );

    const input = screen.getByPlaceholderText(/type your message/i);
    const sendButton = screen.getByRole('button', { name: /send/i });

    // Send a message
    fireEvent.change(input, { target: { value: 'Callback test' } });
    fireEvent.click(sendButton);

    // Callback should be called
    expect(mockOnSendMessage).toHaveBeenCalledWith('Callback test');
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
    expect(receivedMessage.content).toContain('mock response');
  });
});
