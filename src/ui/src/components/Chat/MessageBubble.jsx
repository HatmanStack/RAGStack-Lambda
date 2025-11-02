import React from 'react';

export function MessageBubble({ message }) {
  // Minimal implementation for ChatPanel tests
  return (
    <div className={`message-bubble ${message.type === 'user' ? 'user-message' : 'assistant-message'}`}>
      <div className="message-content">{message.content}</div>
      <div className="message-timestamp">
        {new Date(message.timestamp).toLocaleTimeString()}
      </div>
    </div>
  );
}
