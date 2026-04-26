/**
 * MessageList Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageList } from '../MessageList';
import { ChatMessage, ErrorState } from '../../types';
import { mockScrollIntoView } from '../../test-utils';

describe('MessageList', () => {
  beforeEach(() => {
    // Mock scrollIntoView for auto-scroll tests
    mockScrollIntoView();
  });

  const sampleMessages: ChatMessage[] = [
    {
      role: 'user',
      content: 'Hello',
      timestamp: '2024-01-01T12:00:00Z',
    },
    {
      role: 'assistant',
      content: 'Hi there',
      timestamp: '2024-01-01T12:00:01Z',
    },
    {
      role: 'user',
      content: 'How are you?',
      timestamp: '2024-01-01T12:00:02Z',
    },
  ];

  it('renders all messages in messages array', () => {
    render(<MessageList messages={sampleMessages} isLoading={false} showSources={true} />);

    expect(screen.getByText('Hello')).toBeInTheDocument();
    expect(screen.getByText('Hi there')).toBeInTheDocument();
    expect(screen.getByText('How are you?')).toBeInTheDocument();
  });

  it('scrolls to bottom when messages change', () => {
    const { rerender } = render(
      <MessageList messages={sampleMessages} isLoading={false} showSources={true} />
    );

    // Add a new message
    const updatedMessages = [
      ...sampleMessages,
      {
        role: 'assistant',
        content: 'I am doing well',
        timestamp: '2024-01-01T12:00:03Z',
      },
    ];

    rerender(<MessageList messages={updatedMessages} isLoading={false} showSources={true} />);

    // scrollIntoView should have been called (mocked in beforeEach)
    expect(window.HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it('displays loading indicator when isLoading is true', () => {
    render(<MessageList messages={sampleMessages} isLoading={true} showSources={true} />);

    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
  });

  it('displays error message when error prop is set', () => {
    const error: ErrorState = {
      message: 'Something went wrong',
      retryable: false,
    };

    render(<MessageList messages={sampleMessages} isLoading={false} error={error} showSources={true} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('displays retry button when error is retryable', () => {
    const mockOnRetry = vi.fn();
    const error: ErrorState = {
      message: 'Network error',
      retryable: true,
      onRetry: mockOnRetry,
    };

    render(<MessageList messages={sampleMessages} isLoading={false} error={error} showSources={true} />);

    const retryButton = screen.getByRole('button', { name: /retry/i });
    expect(retryButton).toBeInTheDocument();

    fireEvent.click(retryButton);
    expect(mockOnRetry).toHaveBeenCalledOnce();
  });

  it('does NOT display retry button when error is not retryable', () => {
    const error: ErrorState = {
      message: 'Authentication required',
      retryable: false,
    };

    render(<MessageList messages={sampleMessages} isLoading={false} error={error} showSources={true} />);

    expect(screen.queryByRole('button', { name: /retry/i })).not.toBeInTheDocument();
  });

  it('displays empty state when messages array is empty', () => {
    render(<MessageList messages={[]} isLoading={false} showSources={true} />);

    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument();
  });

  it('does NOT display empty state when loading', () => {
    render(<MessageList messages={[]} isLoading={true} showSources={true} />);

    expect(screen.queryByText(/start a conversation/i)).not.toBeInTheDocument();
    expect(screen.getByText('Assistant is typing')).toBeInTheDocument();
  });
});
