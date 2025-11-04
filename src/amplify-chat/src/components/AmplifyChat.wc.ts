/**
 * AmplifyChat Web Component
 *
 * A custom HTML element that wraps the ChatWithSources React component.
 * This allows the chat component to be used in any framework or vanilla JavaScript.
 *
 * Usage:
 * ```html
 * <script src="https://your-cdn.com/amplify-chat.js"></script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 * ```
 *
 * Attributes:
 * - conversation-id: Unique conversation ID (default: "default")
 * - header-text: Custom header title (default: "Document Q&A")
 * - header-subtitle: Custom subtitle (default: "Ask questions about your documents")
 * - show-sources: Show/hide sources (default: "true")
 * - max-width: Component max-width (default: "100%")
 * - user-id: User ID for authenticated mode (optional)
 * - user-token: Authentication token for authenticated mode (optional)
 * - theme-preset: Theme preset - light, dark, or brand (default: "light")
 * - theme-overrides: JSON string with theme overrides (optional)
 *
 * Events:
 * - amplify-chat:send-message: Fired when user sends a message
 * - amplify-chat:response-received: Fired when AI responds
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { ChatWithSources } from './ChatWithSources';
import type { ChatWithSourcesProps, ChatMessage } from '../types';

/**
 * AmplifyChat Web Component
 *
 * Extends HTMLElement to provide a custom element interface to the
 * ChatWithSources React component.
 */
class AmplifyChat extends HTMLElement {
  private root: Root | null = null;

  /**
   * Observed attributes for reactivity
   */
  static get observedAttributes(): string[] {
    return [
      'conversation-id',
      'header-text',
      'header-subtitle',
      'show-sources',
      'max-width',
      'user-id',
      'user-token',
      'theme-preset',
      'theme-overrides',
    ];
  }

  /**
   * Lifecycle: Element inserted into DOM
   */
  connectedCallback(): void {
    this.render();
  }

  /**
   * Lifecycle: Element removed from DOM
   */
  disconnectedCallback(): void {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }

  /**
   * Lifecycle: Observed attribute changed
   */
  attributeChangedCallback(): void {
    this.render();
  }

  /**
   * Get attribute value with fallback
   */
  private getAttribute(name: string, fallback: string): string {
    return super.getAttribute(name) || fallback;
  }

  /**
   * Get boolean attribute value
   */
  private getBooleanAttribute(name: string, fallback: boolean): boolean {
    const value = super.getAttribute(name);
    if (value === null) return fallback;
    return value !== 'false' && value !== '0';
  }

  /**
   * Get theme overrides from JSON attribute
   */
  private getThemeOverrides(): ChatWithSourcesProps['themeOverrides'] {
    const overridesStr = super.getAttribute('theme-overrides');
    if (!overridesStr) return undefined;

    try {
      return JSON.parse(overridesStr);
    } catch {
      console.warn('Invalid theme-overrides JSON');
      return undefined;
    }
  }

  /**
   * Render the React component into this element
   */
  private render(): void {
    // Create root if it doesn't exist
    if (!this.root) {
      this.root = createRoot(this);
    }

    // Build props from attributes
    const props: ChatWithSourcesProps = {
      conversationId: this.getAttribute(
        'conversation-id',
        'default'
      ),
      headerText: this.getAttribute(
        'header-text',
        'Document Q&A'
      ),
      headerSubtitle: this.getAttribute(
        'header-subtitle',
        'Ask questions about your documents'
      ),
      showSources: this.getBooleanAttribute('show-sources', true),
      maxWidth: this.getAttribute('max-width', '100%'),
      userId: super.getAttribute('user-id') || null,
      userToken: super.getAttribute('user-token') || null,
      themePreset: (super.getAttribute('theme-preset') || 'light') as 'light' | 'dark' | 'brand',
      themeOverrides: this.getThemeOverrides(),
      onSendMessage: (message: string, conversationId: string) => {
        this.dispatchEvent(
          new CustomEvent('amplify-chat:send-message', {
            detail: { message, conversationId },
            bubbles: true,
            composed: true,
          })
        );
      },
      onResponseReceived: (response: ChatMessage) => {
        this.dispatchEvent(
          new CustomEvent('amplify-chat:response-received', {
            detail: response,
            bubbles: true,
            composed: true,
          })
        );
      },
    };

    // Render the component
    this.root.render(
      React.createElement(ChatWithSources, props)
    );
  }

  /**
   * Public API: Programmatically get conversation ID
   */
  getConversationId(): string {
    return this.getAttribute('conversation-id', 'default');
  }

  /**
   * Public API: Programmatically set conversation ID
   */
  setConversationId(id: string): void {
    this.setAttribute('conversation-id', id);
  }
}

/**
 * Register the custom element
 */
if (!customElements.get('amplify-chat')) {
  customElements.define('amplify-chat', AmplifyChat);
}

export { AmplifyChat };
