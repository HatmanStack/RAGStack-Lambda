import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Chat } from './index';

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
    // ChatPanel stub should render "ChatPanel - TODO"
    expect(screen.getByText(/ChatPanel - TODO/i)).toBeInTheDocument();
  });
});
