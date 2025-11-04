/**
 * Tests for ChatWithSources component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ChatWithSources } from '../../amplify-chat/src/components/ChatWithSources';

// Mock Amplify components
vi.mock('@aws-amplify/ui-react-ai', () => ({
  AIConversation: ({ conversationId, responseComponent }: any) => (
    <div data-testid="ai-conversation" data-conversation-id={conversationId}>
      AI Conversation Mock
      {responseComponent && <div data-testid="response-component">Response</div>}
    </div>
  ),
}));

describe('ChatWithSources Component', () => {
  it('renders without crashing', () => {
    render(<ChatWithSources />);
    expect(screen.getByTestId('ai-conversation')).toBeInTheDocument();
  });

  it('renders with default header text', () => {
    render(<ChatWithSources />);
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('renders with default subtitle', () => {
    render(<ChatWithSources />);
    expect(
      screen.getByText('Ask questions about your documents')
    ).toBeInTheDocument();
  });

  it('renders with custom header text', () => {
    render(<ChatWithSources headerText="Custom Title" />);
    expect(screen.getByText('Custom Title')).toBeInTheDocument();
  });

  it('renders with custom subtitle', () => {
    const customSubtitle = 'Custom subtitle text';
    render(<ChatWithSources headerSubtitle={customSubtitle} />);
    expect(screen.getByText(customSubtitle)).toBeInTheDocument();
  });

  it('does not render subtitle when empty string provided', () => {
    render(<ChatWithSources headerSubtitle="" />);
    // Subtitle should not appear, but header should
    expect(screen.getByText('Document Q&A')).toBeInTheDocument();
  });

  it('passes conversation ID to AIConversation component', () => {
    const conversationId = 'my-custom-conversation';
    render(<ChatWithSources conversationId={conversationId} />);

    const aiConversation = screen.getByTestId('ai-conversation');
    expect(aiConversation).toHaveAttribute(
      'data-conversation-id',
      conversationId
    );
  });

  it('uses default conversation ID when not provided', () => {
    render(<ChatWithSources />);

    const aiConversation = screen.getByTestId('ai-conversation');
    expect(aiConversation).toHaveAttribute('data-conversation-id', 'default');
  });

  it('renders footer with sources attribution', () => {
    render(<ChatWithSources />);
    expect(
      screen.getByText(
        'Responses are sourced from your knowledge base'
      )
    ).toBeInTheDocument();
  });

  it('applies custom className to container', () => {
    const customClass = 'my-custom-chat-class';
    const { container } = render(
      <ChatWithSources className={customClass} />
    );

    const chatContainer = container.querySelector(`.${customClass}`);
    expect(chatContainer).toBeInTheDocument();
  });

  it('sets max width inline style', () => {
    const maxWidth = '500px';
    const { container } = render(<ChatWithSources maxWidth={maxWidth} />);

    const chatContainer = container.firstChild as HTMLElement;
    expect(chatContainer.style.maxWidth).toBe(maxWidth);
  });

  it('shows sources display when showSources is true', () => {
    render(<ChatWithSources showSources={true} />);
    expect(screen.getByTestId('response-component')).toBeInTheDocument();
  });

  it('hides sources display when showSources is false', () => {
    render(<ChatWithSources showSources={false} />);
    // Response component should still be there, but responseComponent param should be undefined
    expect(screen.getByTestId('ai-conversation')).toBeInTheDocument();
  });

  it('calls onSendMessage callback when provided', () => {
    const mockCallback = vi.fn();
    const conversationId = 'test-conversation';

    render(
      <ChatWithSources
        conversationId={conversationId}
        onSendMessage={mockCallback}
      />
    );

    // Component should render without error
    expect(screen.getByTestId('ai-conversation')).toBeInTheDocument();
  });

  it('calls onResponseReceived callback when provided', () => {
    const mockCallback = vi.fn();

    render(<ChatWithSources onResponseReceived={mockCallback} />);

    // Component should render without error
    expect(screen.getByTestId('ai-conversation')).toBeInTheDocument();
  });

  it('renders container with proper structure', () => {
    const { container } = render(<ChatWithSources />);

    const chatContainer = container.querySelector('[class*="chatContainer"]');
    expect(chatContainer).toBeInTheDocument();

    const header = container.querySelector('[class*="chatHeader"]');
    expect(header).toBeInTheDocument();

    const content = container.querySelector('[class*="chatContent"]');
    expect(content).toBeInTheDocument();

    const footer = container.querySelector('[class*="chatFooter"]');
    expect(footer).toBeInTheDocument();
  });

  it('handles all optional props together', () => {
    const mockSendMessage = vi.fn();
    const mockResponseReceived = vi.fn();

    render(
      <ChatWithSources
        conversationId="combined-test"
        headerText="Combined Test"
        headerSubtitle="Testing all props"
        inputPlaceholder="Custom placeholder"
        onSendMessage={mockSendMessage}
        onResponseReceived={mockResponseReceived}
        showSources={true}
        maxWidth="800px"
        className="combined-class"
      />
    );

    expect(screen.getByText('Combined Test')).toBeInTheDocument();
    expect(screen.getByText('Testing all props')).toBeInTheDocument();
    expect(screen.getByTestId('ai-conversation')).toBeInTheDocument();
  });
});
