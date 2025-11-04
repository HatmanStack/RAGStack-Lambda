/**
 * Type tests to ensure interfaces are correctly defined.
 */
import { describe, it, expect } from 'vitest';
import type { Source, ChatMessage, ChatWithSourcesProps } from '../src/types';

describe('Type definitions', () => {
  it('Source interface is correctly defined', () => {
    const source: Source = {
      title: 'Test Document',
      location: 'Page 1',
      snippet: 'Sample text',
    };

    expect(source.title).toBe('Test Document');
    expect(source.location).toBe('Page 1');
    expect(source.snippet).toBe('Sample text');
  });

  it('ChatMessage interface includes required fields', () => {
    const message: ChatMessage = {
      role: 'assistant',
      content: 'Hello',
      timestamp: new Date().toISOString(),
    };

    expect(message.role).toBe('assistant');
    expect(message.content).toBe('Hello');
    expect(message.timestamp).toBeDefined();
  });

  it('ChatMessage interface supports modelUsed field', () => {
    const message: ChatMessage = {
      role: 'assistant',
      content: 'Hello',
      timestamp: new Date().toISOString(),
      modelUsed: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    };

    expect(message.modelUsed).toBe('us.anthropic.claude-haiku-4-5-20251001-v1:0');
  });

  it('ChatWithSourcesProps includes auth fields', () => {
    const props: ChatWithSourcesProps = {
      conversationId: 'test',
      userId: 'user123',
      userToken: 'token',
    };

    expect(props.conversationId).toBe('test');
    expect(props.userId).toBe('user123');
    expect(props.userToken).toBe('token');
  });

  it('ChatWithSourcesProps includes theme fields', () => {
    const props: ChatWithSourcesProps = {
      themePreset: 'dark',
      themeOverrides: {
        primaryColor: '#ff9900',
        fontFamily: 'Arial',
        spacing: 'comfortable',
      },
    };

    expect(props.themePreset).toBe('dark');
    expect(props.themeOverrides?.primaryColor).toBe('#ff9900');
    expect(props.themeOverrides?.fontFamily).toBe('Arial');
    expect(props.themeOverrides?.spacing).toBe('comfortable');
  });
});
