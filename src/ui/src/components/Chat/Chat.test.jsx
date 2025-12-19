import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { Chat } from './index';

// Mock scrollIntoView (not available in JSDOM)
Element.prototype.scrollIntoView = vi.fn();

// Mock AWS Amplify API
const mockGraphql = vi.fn();
vi.mock('aws-amplify/api', () => ({
  generateClient: vi.fn(() => ({
    graphql: mockGraphql
  }))
}));

describe('Chat Page', () => {
  beforeEach(() => {
    mockGraphql.mockReset();
    // Default mock returns no CDN URL
    mockGraphql.mockResolvedValue({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: '{}',
          Custom: '{}'
        }
      }
    });
  });

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

  it('shows embed section when CDN URL is available', async () => {
    mockGraphql.mockResolvedValue({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: JSON.stringify({ chat_cdn_url: 'https://example.cloudfront.net/ragstack-chat.js' }),
          Custom: '{}'
        }
      }
    });

    render(<Chat />);

    await waitFor(() => {
      expect(screen.getByText(/Embed Chat Widget/i)).toBeInTheDocument();
    });
  });

  it('shows embed section with placeholder when CDN URL is not available', async () => {
    mockGraphql.mockResolvedValue({
      data: {
        getConfiguration: {
          Schema: '{}',
          Default: '{}',
          Custom: '{}'
        }
      }
    });

    render(<Chat />);

    // Embed section should always be shown (with placeholder URL if CDN not configured)
    expect(screen.getByText(/Embed Chat Widget/i)).toBeInTheDocument();
  });
});
