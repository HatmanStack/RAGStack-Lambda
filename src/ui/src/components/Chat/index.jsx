import React from 'react';
import { ContentLayout, Header } from '@cloudscape-design/components';
import { ChatPanel } from './ChatPanel';

export function Chat() {
  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Ask questions about your documents using natural language"
        >
          Knowledge Base Chat
        </Header>
      }
    >
      <ChatPanel />
    </ContentLayout>
  );
}
