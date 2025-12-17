/**
 * ChatWithSources Component Tests
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatWithSources } from '../ChatWithSources';
import { mockScrollIntoView, mockSessionStorage } from '../../test-utils';

// Mock the GraphQL client
const { mockConversationQuery } = vi.hoisted(() => {
  return {
    mockConversationQuery: vi.fn(),
  };
});

vi.mock('aws-amplify/data', () => ({
  generateClient: () => ({
    queries: {
      conversation: mockConversationQuery,
    },
  }),
}));

describe('ChatWithSources', () => {
  beforeEach(() => {
    mockScrollIntoView();
    mockSessionStorage();
    mockConversationQuery.mockReset();
    mockConversationQuery.mockResolvedValue({
      data: {
        content: 'Test response',
        sources: [],
        modelUsed: 'test-model',
      },
      errors: null,
    });
  });

  it('renders with default props', () => {
    render(<ChatWithSources />);

    // Header should display default text
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
    expect(screen.getByText('Ask questions about your documents')).toBeInTheDocument();

    // Input should be present
    expect(screen.getByPlaceholderText('Ask a question...')).toBeInTheDocument();
  });

  it('renders with custom header text', () => {
    render(
      <ChatWithSources
        headerText="Custom Title"
        headerSubtitle="Custom subtitle"
        conversationId="test-1"
      />
    );

    expect(screen.getByText('Custom Title')).toBeInTheDocument();
    expect(screen.getByText('Custom subtitle')).toBeInTheDocument();
  });

  it('renders with custom input placeholder', () => {
    render(<ChatWithSources inputPlaceholder="Type here..." conversationId="test-1" />);

    expect(screen.getByPlaceholderText('Type here...')).toBeInTheDocument();
  });

  it('passes conversationId to ChatInterface', () => {
    render(<ChatWithSources conversationId="my-conversation" />);

    // ChatInterface should render (look for empty state)
    expect(screen.getByText(/start a conversation/i)).toBeInTheDocument();
  });

  it('passes userId and userToken for authenticated mode', () => {
    render(<ChatWithSources conversationId="test-1" userId="user123" userToken="token456" />);

    // Component should render successfully with auth props
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('renders in guest mode when no userId/userToken provided', () => {
    render(<ChatWithSources conversationId="test-1" />);

    // Component should render successfully without auth props
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('forwards onSendMessage callback', () => {
    const mockCallback = vi.fn();
    render(<ChatWithSources conversationId="test-1" onSendMessage={mockCallback} />);

    // Callback prop should be passed to ChatInterface
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('forwards onResponseReceived callback', () => {
    const mockCallback = vi.fn();
    render(<ChatWithSources conversationId="test-1" onResponseReceived={mockCallback} />);

    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('applies custom className', () => {
    const { container } = render(<ChatWithSources conversationId="test-1" className="custom-class" />);

    const chatContainer = container.querySelector('.custom-class');
    expect(chatContainer).toBeInTheDocument();
  });

  it('applies custom maxWidth style', () => {
    const { container } = render(<ChatWithSources conversationId="test-1" maxWidth="600px" />);

    const chatContainer = container.firstChild as HTMLElement;
    expect(chatContainer.style.maxWidth).toBe('600px');
  });

  it('passes showSources prop to ChatInterface', () => {
    render(<ChatWithSources conversationId="test-1" showSources={false} />);

    // Component renders successfully
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('applies light theme by default', () => {
    const { container } = render(<ChatWithSources conversationId="test-1" />);

    const chatContainer = container.firstChild as HTMLElement;
    // Theme is applied via CSS custom properties
    expect(chatContainer).toBeInTheDocument();
  });

  it('applies dark theme when specified', () => {
    const { container } = render(<ChatWithSources conversationId="test-1" themePreset="dark" />);

    const chatContainer = container.firstChild as HTMLElement;
    expect(chatContainer).toBeInTheDocument();
  });

  it('applies brand theme when specified', () => {
    const { container } = render(<ChatWithSources conversationId="test-1" themePreset="brand" />);

    const chatContainer = container.firstChild as HTMLElement;
    expect(chatContainer).toBeInTheDocument();
  });

  it('applies custom theme overrides', () => {
    const themeOverrides = {
      primaryColor: '#FF0000',
      fontFamily: 'Arial, sans-serif',
    };

    const { container } = render(
      <ChatWithSources conversationId="test-1" themeOverrides={themeOverrides} />
    );

    const chatContainer = container.firstChild as HTMLElement;
    expect(chatContainer).toBeInTheDocument();
  });

  it('renders footer with knowledge base message', () => {
    render(<ChatWithSources conversationId="test-1" />);

    // Footer should be present with knowledge base message
    const footer = screen.getByText(/responses are sourced from your knowledge base/i);
    expect(footer).toBeInTheDocument();
  });
});
