/**
 * MessageInput Component
 *
 * Text input with send button for user messages.
 * Features: auto-resize textarea, Enter/Shift+Enter handling, validation.
 */

import React, { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { MessageInputProps } from '../types';
import styles from './MessageInput.module.css';

/**
 * MessageInput Component
 *
 * Presentational component that captures user input and validates locally.
 * Parent component (ChatInterface) handles what happens after onSend.
 *
 * @param onSend - Callback when message should be sent
 * @param isLoading - Loading state (disables input during send)
 * @param placeholder - Placeholder text for textarea
 */
export const MessageInput: React.FC<MessageInputProps> = ({
  onSend,
  isLoading,
  placeholder = 'Type your message...',
}) => {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea as user types
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight}px`;
    }
  }, [value]);

  // Handle input change
  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
  };

  // Handle send (called by button click or Enter key)
  const handleSend = () => {
    const trimmed = value.trim();

    // Validate: don't send empty/whitespace-only messages
    if (!trimmed || isLoading) {
      return;
    }

    // Call parent callback and clear input
    onSend(trimmed);
    setValue('');
  };

  // Handle Enter key (Enter = send, Shift+Enter = newline)
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Determine if send button should be disabled
  const isSendDisabled = isLoading || !value.trim();

  return (
    <div className={styles.inputContainer}>
      <div className={styles.inputWrapper}>
        <textarea
          ref={textareaRef}
          className={styles.textarea}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          rows={1}
        />
        <button
          className={styles.sendButton}
          onClick={handleSend}
          disabled={isSendDisabled}
          type="button"
        >
          Send
        </button>
      </div>
    </div>
  );
};

export default MessageInput;
