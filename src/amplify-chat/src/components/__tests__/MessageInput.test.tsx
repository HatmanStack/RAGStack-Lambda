/**
 * MessageInput Component Tests
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MessageInput } from '../MessageInput';

describe('MessageInput', () => {
  it('renders textarea and send button', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('calls onSend with message text when send button clicked', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(textarea, { target: { value: 'Hello world' } });
    fireEvent.click(sendButton);

    expect(mockOnSend).toHaveBeenCalledWith('Hello world');
  });

  it('calls onSend when Enter key is pressed', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Type your message...');

    fireEvent.change(textarea, { target: { value: 'Test message' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    expect(mockOnSend).toHaveBeenCalledWith('Test message');
  });

  it('does NOT call onSend when Shift+Enter is pressed (creates newline instead)', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Type your message...');

    fireEvent.change(textarea, { target: { value: 'Line 1' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  it('does not call onSend when message is empty', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.click(sendButton);

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  it('does not call onSend when message is only whitespace', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(textarea, { target: { value: '   ' } });
    fireEvent.click(sendButton);

    expect(mockOnSend).not.toHaveBeenCalled();
  });

  it('clears input after successful send', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const textarea = screen.getByPlaceholderText(
      'Type your message...'
    ) as HTMLTextAreaElement;
    const sendButton = screen.getByRole('button', { name: /send/i });

    fireEvent.change(textarea, { target: { value: 'Test message' } });
    fireEvent.click(sendButton);

    expect(textarea.value).toBe('');
  });

  it('disables send button when isLoading is true', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={true} />);

    const sendButton = screen.getByRole('button', { name: /send/i });

    expect(sendButton).toBeDisabled();
  });

  it('disables send button when input is empty', () => {
    const mockOnSend = vi.fn();
    render(<MessageInput onSend={mockOnSend} isLoading={false} />);

    const sendButton = screen.getByRole('button', { name: /send/i });

    expect(sendButton).toBeDisabled();
  });
});
