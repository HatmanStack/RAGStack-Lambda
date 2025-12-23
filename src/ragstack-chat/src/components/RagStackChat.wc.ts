/**
 * RagStackChat Web Component
 *
 * A custom HTML element that wraps the ChatWithSources React component.
 * This allows the chat component to be used in any framework or vanilla JavaScript.
 *
 * Usage:
 * ```html
 * <script src="https://your-cdn.com/ragstack-chat.js"></script>
 * <ragstack-chat conversation-id="my-chat"></ragstack-chat>
 * ```
 *
 * Attributes:
 * - conversation-id: Unique conversation ID (default: "default")
 * - header-text: Custom header title (default: "Document Q&A")
 * - header-subtitle: Custom subtitle (default: "Ask questions about your documents")
 * - input-placeholder: Custom input placeholder (default: "Ask a question...")
 * - show-sources: Show/hide sources (default: "true")
 * - max-width: Component max-width (default: "100%")
 * - user-id: User ID for authenticated mode (optional)
 * - user-token: Authentication token for authenticated mode (optional)
 *
 * Events:
 * - ragstack-chat:send-message: Fired when user sends a message
 * - ragstack-chat:response-received: Fired when AI responds
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { ChatWithSources } from './ChatWithSources';
import type { ChatWithSourcesProps, ChatMessage } from '../types';

/**
 * RagStackChat Web Component
 *
 * Extends HTMLElement to provide a custom element interface to the
 * ChatWithSources React component.
 */
class RagStackChat extends HTMLElement {
  private root: Root | null = null;

  /**
   * Observed attributes for reactivity
   */
  static get observedAttributes(): string[] {
    return [
      'conversation-id',
      'header-text',
      'header-subtitle',
      'input-placeholder',
      'show-sources',
      'max-width',
      'user-id',
      'user-token',
    ];
  }

  /**
   * Lifecycle: Element inserted into DOM
   */
  connectedCallback(): void {
    try {
      this.render();
    } catch (error) {
      console.error('[RagStackChat] Error in connectedCallback:', error);
      throw error;
    }
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
  private getAttributeWithFallback(name: string, fallback: string): string {
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
   * Render the React component into this element
   */
  private render(): void {
    try {
      // Create root if it doesn't exist
      if (!this.root) {
        this.root = createRoot(this);
      }

      const props: ChatWithSourcesProps = {
        conversationId: this.getAttributeWithFallback(
          'conversation-id',
          'default'
        ),
        headerText: this.getAttributeWithFallback(
          'header-text',
          'Document Q&A'
        ),
        headerSubtitle: this.getAttributeWithFallback(
          'header-subtitle',
          'Ask questions about your documents'
        ),
        inputPlaceholder: this.getAttributeWithFallback(
          'input-placeholder',
          'Ask a question...'
        ),
        showSources: this.getBooleanAttribute('show-sources', true),
        maxWidth: this.getAttributeWithFallback('max-width', '100%'),
        userId: super.getAttribute('user-id') || null,
        userToken: super.getAttribute('user-token') || null,
        onSendMessage: (message: string, conversationId: string) => {
          this.dispatchEvent(
            new CustomEvent('ragstack-chat:send-message', {
              detail: { message, conversationId },
              bubbles: true,
              composed: true,
            })
          );
        },
        onResponseReceived: (response: ChatMessage) => {
          this.dispatchEvent(
            new CustomEvent('ragstack-chat:response-received', {
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

    } catch (error) {
      console.error('[RagStackChat] Error in render():', error);
      // SECURITY: Use DOM construction with textContent instead of innerHTML template literals.
      // The previous implementation used innerHTML with ${error.message} which is vulnerable
      // to XSS if an attacker can control the error message content (e.g., through malformed
      // configuration or crafted API responses). textContent automatically escapes HTML entities.
      const errorDiv = document.createElement('div');
      errorDiv.style.cssText = 'padding: 20px; border: 2px solid red; background: #fee; color: #c00;';
      const h3 = document.createElement('h3');
      h3.textContent = 'RagStackChat Error';
      const p = document.createElement('p');
      p.textContent = 'Failed to render chat component. Check console for details.';
      const pre = document.createElement('pre');
      // textContent safely escapes any HTML in the error message
      pre.textContent = error instanceof Error ? error.message : String(error);
      errorDiv.append(h3, p, pre);
      this.innerHTML = '';  // Clear existing content before appending
      this.appendChild(errorDiv);
      throw error;
    }
  }

  /**
   * Public API: Programmatically get conversation ID
   */
  getConversationId(): string {
    return this.getAttributeWithFallback('conversation-id', 'default');
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
if (!customElements.get('ragstack-chat')) {
  customElements.define('ragstack-chat', RagStackChat);
}

export { RagStackChat };
