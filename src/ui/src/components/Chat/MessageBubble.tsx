import React from 'react';
import { Box, SpaceBetween } from '@cloudscape-design/components';
import { SourceList } from './SourceList';

export function MessageBubble({ message }) {
  const isUser = message.type === 'user';
  const timestamp = new Date(message.timestamp).toLocaleTimeString();

  return (
    <div className={`message-bubble ${isUser ? 'user-message' : 'assistant-message'}`}>
      <SpaceBetween size="s">
        <Box>
          <div className="message-content" style={{ whiteSpace: 'pre-wrap' }}>
            {message.content}
          </div>
          <div className="message-timestamp">{timestamp}</div>
        </Box>

        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}
      </SpaceBetween>
    </div>
  );
}
