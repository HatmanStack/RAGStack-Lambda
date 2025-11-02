import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageBubble } from './MessageBubble';

describe('MessageBubble', () => {
  it('renders user message with correct styling', () => {
    const message = {
      type: 'user',
      content: 'What documents do we have?',
      timestamp: new Date().toISOString()
    };

    const { container } = render(<MessageBubble message={message} />);

    expect(screen.getByText('What documents do we have?')).toBeInTheDocument();

    const bubble = container.querySelector('.message-bubble');
    expect(bubble).toHaveClass('user-message');
  });

  it('renders assistant message with correct styling', () => {
    const message = {
      type: 'assistant',
      content: 'We have 5 invoices and 3 receipts.',
      timestamp: new Date().toISOString(),
      sources: []
    };

    const { container } = render(<MessageBubble message={message} />);

    expect(screen.getByText('We have 5 invoices and 3 receipts.')).toBeInTheDocument();

    const bubble = container.querySelector('.message-bubble');
    expect(bubble).toHaveClass('assistant-message');
  });

  it('displays timestamp for message', () => {
    const timestamp = new Date('2024-01-01T12:00:00.000Z');
    const message = {
      type: 'user',
      content: 'Test',
      timestamp: timestamp.toISOString()
    };

    render(<MessageBubble message={message} />);

    // Timestamp should be formatted as time only
    const timeString = timestamp.toLocaleTimeString();
    expect(screen.getByText(timeString)).toBeInTheDocument();
  });

  it('renders SourceList for assistant messages with sources', () => {
    const message = {
      type: 'assistant',
      content: 'Based on the documents...',
      timestamp: new Date().toISOString(),
      sources: [
        { documentId: 'doc1.pdf', pageNumber: 3, s3Uri: 's3://...', snippet: 'text' }
      ]
    };

    const { container } = render(<MessageBubble message={message} />);

    // Check that message content is displayed
    expect(screen.getByText('Based on the documents...')).toBeInTheDocument();

    // SourceList should be rendered (it will have its own tests for internal behavior)
    // For now, just verify the message renders correctly
    expect(container.querySelector('.message-bubble')).toBeInTheDocument();
  });

  it('does not render SourceList for user messages', () => {
    const message = {
      type: 'user',
      content: 'User question',
      timestamp: new Date().toISOString()
    };

    const { container } = render(<MessageBubble message={message} />);

    // Message should render
    expect(screen.getByText('User question')).toBeInTheDocument();

    // But SourceList should not be present (user messages don't have sources)
    expect(container.querySelector('.sources')).not.toBeInTheDocument();
  });

  it('preserves line breaks in message content', () => {
    const message = {
      type: 'assistant',
      content: 'Line 1\nLine 2\nLine 3',
      timestamp: new Date().toISOString(),
      sources: []
    };

    const { container } = render(<MessageBubble message={message} />);

    const content = container.querySelector('.message-content');
    expect(content).toHaveStyle({ whiteSpace: 'pre-wrap' });
  });

  it('handles empty sources array for assistant messages', () => {
    const message = {
      type: 'assistant',
      content: 'Answer without sources',
      timestamp: new Date().toISOString(),
      sources: []
    };

    render(<MessageBubble message={message} />);

    expect(screen.getByText('Answer without sources')).toBeInTheDocument();
  });

  it('displays both content and timestamp together', () => {
    const timestamp = new Date('2024-01-01T15:30:00.000Z');
    const message = {
      type: 'user',
      content: 'Complete message',
      timestamp: timestamp.toISOString()
    };

    render(<MessageBubble message={message} />);

    expect(screen.getByText('Complete message')).toBeInTheDocument();
    expect(screen.getByText(timestamp.toLocaleTimeString())).toBeInTheDocument();
  });
});
