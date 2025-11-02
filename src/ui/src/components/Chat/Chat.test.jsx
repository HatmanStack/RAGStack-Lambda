import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Chat } from './index';

// Mock scrollIntoView (not available in JSDOM)
Element.prototype.scrollIntoView = vi.fn();

// Mock AWS Amplify API
vi.mock('aws-amplify/api', () => ({
  generateClient: vi.fn(() => ({
    graphql: vi.fn()
  }))
}));

describe('Chat Page', () => {
  it('renders header', () => {
    render(<Chat />);
    expect(screen.getByText(/Knowledge Base Chat/i)).toBeInTheDocument();
  });

  it('renders description', () => {
    render(<Chat />);
    expect(screen.getByText(/Ask questions about your documents/i)).toBeInTheDocument();
  });

  it('renders ChatPanel component', () => {
    render(<Chat />);
    // ChatPanel should render with empty state
    expect(screen.getByText(/Start a conversation/i)).toBeInTheDocument();
  });
});
