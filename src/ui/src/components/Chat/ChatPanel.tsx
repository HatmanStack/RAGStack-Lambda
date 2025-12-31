import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
  Container,
  SpaceBetween,
  FormField,
  Input,
  Button,
  Alert,
  Box
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { queryKnowledgeBase } from '../../graphql/queries/queryKnowledgeBase';
import type { GqlResponse } from '../../types/graphql';
import { MessageBubble } from './MessageBubble';
import './ChatPanel.css';

interface ChatResponse {
  answer: string;
  sources?: unknown[];
  sessionId?: string;
  error?: string;
}

export function ChatPanel() {
  // State management
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionId, setSessionId] = useState(null);

  // Refs
  const messagesEndRef = useRef(null);
  const client = useMemo(() => generateClient(), []);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle sending a message
  const handleSend = async () => {
    const userMessage = inputValue.trim();

    // Validate input
    if (!userMessage) {
      return;
    }

    // Create user message object
    const userMessageObj = {
      type: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };

    // Add user message to messages immediately
    setMessages(prev => [...prev, userMessageObj]);

    // Clear input and set loading state
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      // Call GraphQL API
      const response = await client.graphql({
        query: queryKnowledgeBase,
        variables: {
          query: userMessage,
          sessionId: sessionId  // null for first message
        }
      }) as GqlResponse;

      const data = response.data?.queryKnowledgeBase as ChatResponse | undefined;

      // Check for backend error
      if (data?.error) {
        setError(data.error);
        setSessionId(null);  // Reset session on error
        return;
      }

      // Create AI message object
      const aiMessageObj = {
        type: 'assistant',
        content: data?.answer || '',
        sources: data?.sources || [],
        timestamp: new Date().toISOString()
      };

      // Add AI message and update session
      setMessages(prev => [...prev, aiMessageObj]);
      setSessionId(data?.sessionId || null);

    } catch (err) {
      console.error('[ChatPanel] Chat error:', err);
      setError(`Failed to get response: ${err.message || 'Unknown error'}`);
    } finally {
      setIsLoading(false);
    }
  };

  // Handle Enter key press
  const handleKeyPress = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  // Handle new chat
  const handleNewChat = () => {
    setMessages([]);
    setSessionId(null);
    setError(null);
    setInputValue('');
  };

  return (
    <Container
      header={
        <Box float="right">
          <Button
            onClick={handleNewChat}
            disabled={messages.length === 0}
          >
            New Chat
          </Button>
        </Box>
      }
    >
      <SpaceBetween size="l">
        {error && (
          <Alert
            type="error"
            dismissible
            onDismiss={() => setError(null)}
          >
            {error}
          </Alert>
        )}

        <div className="chat-messages-container">
          {messages.length === 0 && (
            <Box textAlign="center" color="text-body-secondary" padding="xxl">
              Start a conversation by asking a question about your documents
            </Box>
          )}

          {messages.map((msg, idx) => (
            <MessageBubble key={idx} message={msg} />
          ))}

          {isLoading && (
            <div className="loader">
              <div className="loader-dot"></div>
              <div className="loader-dot"></div>
              <div className="loader-dot"></div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <FormField>
          <SpaceBetween direction="horizontal" size="xs">
            <Input
              value={inputValue}
              onChange={({ detail }) => setInputValue(detail.value)}
              onKeyDown={handleKeyPress}
              placeholder="Ask a question..."
              disabled={isLoading}
            />
            <Button
              variant="primary"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              Send
            </Button>
          </SpaceBetween>
        </FormField>
      </SpaceBetween>
    </Container>
  );
}
