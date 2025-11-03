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
import { MessageBubble } from './MessageBubble';
import './ChatPanel.css';

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

  // Debug: Log when component mounts
  useEffect(() => {
    console.log('[ChatPanel] Component mounted');
    console.log('[ChatPanel] Amplify client:', client);
  }, [client]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handle sending a message
  const handleSend = async () => {
    const userMessage = inputValue.trim();

    console.log('[ChatPanel] handleSend called');
    console.log('[ChatPanel] User message:', userMessage);
    console.log('[ChatPanel] Current sessionId:', sessionId);

    // Validate input
    if (!userMessage) {
      console.log('[ChatPanel] Empty message, returning');
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
      console.log('[ChatPanel] Calling GraphQL API...');
      console.log('[ChatPanel] Variables:', { query: userMessage, sessionId });

      // Call GraphQL API
      const response = await client.graphql({
        query: queryKnowledgeBase,
        variables: {
          query: userMessage,
          sessionId: sessionId  // null for first message
        }
      });

      console.log('[ChatPanel] Raw GraphQL response:', response);

      const data = response.data.queryKnowledgeBase;
      console.log('[ChatPanel] Extracted data:', data);

      // Check for backend error
      if (data.error) {
        console.error('[ChatPanel] Backend error:', data.error);
        setError(data.error);
        setSessionId(null);  // Reset session on error
        return;
      }

      console.log('[ChatPanel] Answer:', data.answer);
      console.log('[ChatPanel] Answer length:', data.answer?.length);
      console.log('[ChatPanel] SessionId:', data.sessionId);
      console.log('[ChatPanel] Sources:', data.sources);
      console.log('[ChatPanel] Error field:', data.error);

      // Create AI message object
      const aiMessageObj = {
        type: 'assistant',
        content: data.answer,
        sources: data.sources || [],
        timestamp: new Date().toISOString()
      };

      console.log('[ChatPanel] AI message object:', aiMessageObj);

      // Add AI message and update session
      setMessages(prev => {
        const newMessages = [...prev, aiMessageObj];
        console.log('[ChatPanel] Updated messages:', newMessages);
        return newMessages;
      });
      setSessionId(data.sessionId);
      console.log('[ChatPanel] Updated sessionId to:', data.sessionId);

    } catch (err) {
      console.error('[ChatPanel] Chat error:', err);
      console.error('[ChatPanel] Error details:', {
        message: err.message,
        errors: err.errors,
        stack: err.stack
      });
      setError(`Failed to get response: ${err.message || 'Unknown error'}. Check console for details.`);
    } finally {
      console.log('[ChatPanel] Setting isLoading to false');
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
