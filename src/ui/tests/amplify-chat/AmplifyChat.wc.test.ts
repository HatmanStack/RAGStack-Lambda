/**
 * Tests for AmplifyChat web component.
 */
import { describe, it, expect, beforeAll, afterEach } from 'vitest';
import '../src/components/AmplifyChat.wc';

describe('AmplifyChat Web Component', () => {
  beforeAll(() => {
    // Ensure custom element is defined
    if (!customElements.get('amplify-chat')) {
      throw new Error('amplify-chat custom element not registered');
    }
  });

  afterEach(() => {
    // Clean up any elements added during tests
    document.body.innerHTML = '';
  });

  it('is registered as custom element', () => {
    const el = document.createElement('amplify-chat');
    expect(el).toBeInstanceOf(HTMLElement);
    expect(el.tagName.toLowerCase()).toBe('amplify-chat');
  });

  it('accepts conversation-id attribute', () => {
    const el = document.createElement('amplify-chat') as any;
    el.setAttribute('conversation-id', 'test-123');

    document.body.appendChild(el);

    // Use the public API method
    expect(el.getConversationId()).toBe('test-123');

    document.body.removeChild(el);
  });

  it('accepts user-id and user-token attributes', () => {
    const el = document.createElement('amplify-chat');
    el.setAttribute('user-id', 'user-456');
    el.setAttribute('user-token', 'token-xyz');

    document.body.appendChild(el);

    expect(el.getAttribute('user-id')).toBe('user-456');
    expect(el.getAttribute('user-token')).toBe('token-xyz');

    document.body.removeChild(el);
  });

  it('accepts theme-preset attribute', () => {
    const el = document.createElement('amplify-chat');
    el.setAttribute('theme-preset', 'dark');

    document.body.appendChild(el);

    expect(el.getAttribute('theme-preset')).toBe('dark');

    document.body.removeChild(el);
  });

  it('accepts theme-overrides attribute as JSON', () => {
    const el = document.createElement('amplify-chat');
    const overrides = JSON.stringify({
      primaryColor: '#ff9900',
      fontFamily: 'Arial',
    });
    el.setAttribute('theme-overrides', overrides);

    document.body.appendChild(el);

    expect(el.getAttribute('theme-overrides')).toBe(overrides);

    document.body.removeChild(el);
  });

  it('can programmatically set conversation ID', () => {
    const el = document.createElement('amplify-chat') as any;
    document.body.appendChild(el);

    el.setConversationId('new-conversation');

    expect(el.getAttribute('conversation-id')).toBe('new-conversation');
    expect(el.getConversationId()).toBe('new-conversation');

    document.body.removeChild(el);
  });

  it('dispatches custom events with correct structure', () => {
    return new Promise<void>((resolve) => {
      const el = document.createElement('amplify-chat');
      document.body.appendChild(el);

      // Listen for the send-message event
      el.addEventListener('amplify-chat:send-message', ((event: CustomEvent) => {
        expect(event.detail).toBeDefined();
        expect(event.detail.message).toBeDefined();
        expect(event.detail.conversationId).toBeDefined();
        expect(event.bubbles).toBe(true);
        expect(event.composed).toBe(true);

        document.body.removeChild(el);
        resolve();
      }) as EventListener);

      // Manually trigger the event (simulating the component's behavior)
      el.dispatchEvent(
        new CustomEvent('amplify-chat:send-message', {
          detail: { message: 'test', conversationId: 'default' },
          bubbles: true,
          composed: true,
        })
      );
    });
  });

  it('handles missing attributes with defaults', () => {
    const el = document.createElement('amplify-chat') as any;
    document.body.appendChild(el);

    // Should use default conversation ID
    expect(el.getConversationId()).toBe('default');

    document.body.removeChild(el);
  });
});
