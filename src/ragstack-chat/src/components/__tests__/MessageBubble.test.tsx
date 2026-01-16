/**
 * MessageBubble Component Tests
 */

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageBubble } from '../MessageBubble';
import { ChatMessage } from '../../types';

describe('MessageBubble', () => {
  const userMessage: ChatMessage = {
    role: 'user',
    content: 'Hello, this is a user message',
    timestamp: '2024-01-01T12:00:00Z',
  };

  const assistantMessage: ChatMessage = {
    role: 'assistant',
    content: 'Hello, this is an assistant message',
    timestamp: '2024-01-01T12:00:01Z',
  };

  const assistantMessageWithSources: ChatMessage = {
    role: 'assistant',
    content: 'This is an assistant message with sources',
    timestamp: '2024-01-01T12:00:01Z',
    sources: [
      {
        title: 'Test Source Title',
        filename: 'test-document.pdf',
        location: 'Page 1',
        snippet: 'This is a snippet from the document',
      },
    ],
    modelUsed: 'claude-haiku',
  };

  it('renders user message with correct content', () => {
    render(<MessageBubble message={userMessage} showSources={true} />);
    expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument();
  });

  it('renders assistant message with correct content', () => {
    render(<MessageBubble message={assistantMessage} showSources={true} />);
    expect(screen.getByText('Hello, this is an assistant message')).toBeInTheDocument();
  });

  it('renders SourcesDisplay when assistant message has sources', () => {
    render(<MessageBubble message={assistantMessageWithSources} showSources={true} />);

    // Check that message content is present
    expect(screen.getByText('This is an assistant message with sources')).toBeInTheDocument();

    // Check that sources section header is rendered
    const sourcesHeader = screen.getByText('Sources');
    expect(sourcesHeader).toBeInTheDocument();

    // Verify sources are collapsed by default (snippet not visible)
    expect(screen.queryByText('This is a snippet from the document')).not.toBeInTheDocument();

    // Verify aria-expanded is false by default
    const sourcesButton = sourcesHeader.closest('[role="button"]');
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');

    // Click header to expand
    fireEvent.click(sourcesHeader);

    // Verify aria-expanded is now true
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');

    // Check that source content is visible after expansion
    expect(screen.getByText('This is a snippet from the document')).toBeInTheDocument();
  });

  it('does NOT render SourcesDisplay when showSources is false', () => {
    render(<MessageBubble message={assistantMessageWithSources} showSources={false} />);

    // Message content should still be present
    expect(screen.getByText('This is an assistant message with sources')).toBeInTheDocument();

    // Sources section should NOT be rendered
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
  });

  it('does NOT render SourcesDisplay when sources array is empty', () => {
    const messageWithoutSources: ChatMessage = {
      ...assistantMessage,
      sources: [],
    };

    render(<MessageBubble message={messageWithoutSources} showSources={true} />);

    // Message content should be present
    expect(screen.getByText('Hello, this is an assistant message')).toBeInTheDocument();

    // Sources section should NOT be rendered
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
  });

  it('does NOT render SourcesDisplay for user messages', () => {
    const userMessageWithSources: ChatMessage = {
      ...userMessage,
      sources: [
        {
          title: 'User Source',
          filename: 'user-doc.pdf',
          location: 'Page 1',
          snippet: 'This should not be displayed',
        },
      ],
    };

    render(<MessageBubble message={userMessageWithSources} showSources={true} />);

    // Message content should be present
    expect(screen.getByText('Hello, this is a user message')).toBeInTheDocument();

    // Sources should NOT be rendered for user messages
    expect(screen.queryByText('Sources')).not.toBeInTheDocument();
  });

  it('renders model badge when modelUsed is provided', () => {
    render(<MessageBubble message={assistantMessageWithSources} showSources={true} />);

    expect(screen.getByText('Model: claude-haiku')).toBeInTheDocument();
  });

  it('supports keyboard navigation for collapsible sources (Enter key)', () => {
    render(<MessageBubble message={assistantMessageWithSources} showSources={true} />);

    const sourcesHeader = screen.getByText('Sources');
    const sourcesButton = sourcesHeader.closest('[role="button"]');

    // Verify sources are collapsed by default (snippet not visible)
    expect(screen.queryByText('This is a snippet from the document')).not.toBeInTheDocument();
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');

    // Press Enter to expand
    fireEvent.keyDown(sourcesButton!, { key: 'Enter' });

    // Verify sources are now expanded (snippet visible)
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('This is a snippet from the document')).toBeInTheDocument();
  });

  it('supports keyboard navigation for collapsible sources (Space key)', () => {
    render(<MessageBubble message={assistantMessageWithSources} showSources={true} />);

    const sourcesHeader = screen.getByText('Sources');
    const sourcesButton = sourcesHeader.closest('[role="button"]');

    // Verify sources are collapsed by default (snippet not visible)
    expect(screen.queryByText('This is a snippet from the document')).not.toBeInTheDocument();
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'false');

    // Press Space to expand
    fireEvent.keyDown(sourcesButton!, { key: ' ' });

    // Verify sources are now expanded (snippet visible)
    expect(sourcesButton).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByText('This is a snippet from the document')).toBeInTheDocument();
  });
});
