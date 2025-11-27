/**
 * AmplifyChat Web Component
 *
 * A custom HTML element that wraps the ChatWithSources React component.
 * This allows the chat component to be used in any framework or vanilla JavaScript.
 *
 * **Theming:** Theme configuration (preset, colors, fonts) is embedded at build time
 * from the Settings UI configuration. Override per-instance using attributes.
 *
 * Usage:
 * ```html
 * <script src="https://your-cdn.com/amplify-chat.js"></script>
 * <!-- Uses theme from Settings (embedded at build time) -->
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 * ```
 *
 * Override theme per instance:
 * ```html
 * <amplify-chat
 *   conversation-id="my-chat"
 *   theme-preset="dark"
 *   theme-overrides='{"primaryColor": "#9c27b0"}'
 * ></amplify-chat>
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
 * - theme-preset: Theme preset - light, dark, or brand (default from build config)
 * - theme-overrides: JSON string with theme overrides (default from build config)
 *
 * Events:
 * - amplify-chat:send-message: Fired when user sends a message
 * - amplify-chat:response-received: Fired when AI responds
 */

import React from 'react';
import { createRoot, Root } from 'react-dom/client';
import { ChatWithSources } from './ChatWithSources';
import type { ChatWithSourcesProps, ChatMessage } from '../types';
import { THEME_CONFIG } from '../amplify-config.generated';
import { fetchThemeConfig, ThemeConfig } from '../utils/fetchThemeConfig';

/**
 * AmplifyChat Web Component
 *
 * Extends HTMLElement to provide a custom element interface to the
 * ChatWithSources React component.
 */
class AmplifyChat extends HTMLElement {
  private root: Root | null = null;
  private fetchedTheme: ThemeConfig | null = null;
  private themeFetched = false;

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
      'theme-preset',
      'theme-overrides',
    ];
  }

  /**
   * Lifecycle: Element inserted into DOM
   */
  connectedCallback(): void {
    try {
      console.log('[AmplifyChat] connectedCallback - element added to DOM');

      // Check if theme attributes are provided
      const hasThemeAttrs = this.hasAttribute('theme-preset') ||
                           this.hasAttribute('theme-overrides');

      if (hasThemeAttrs) {
        // Use provided attributes, don't fetch
        console.log('[AmplifyChat] Using theme from attributes');
        this.render();
      } else if (!this.themeFetched) {
        // No attributes provided, fetch theme from SAM API
        console.log('[AmplifyChat] Fetching theme from API...');
        this.fetchAndApplyTheme();
      } else {
        this.render();
      }

      console.log('[AmplifyChat] render() completed successfully');
    } catch (error) {
      console.error('[AmplifyChat] Error in connectedCallback:', error);
      throw error;
    }
  }

  /**
   * Fetch theme configuration from SAM API and apply it
   */
  private async fetchAndApplyTheme(): Promise<void> {
    try {
      const theme = await fetchThemeConfig();

      if (theme) {
        this.themeFetched = true;
        this.fetchedTheme = theme;
        console.log('[AmplifyChat] Theme fetched successfully:', theme);
      } else {
        console.log('[AmplifyChat] No theme fetched, using defaults');
      }
    } catch (error) {
      console.warn('[AmplifyChat] Theme fetch failed, using defaults:', error);
    } finally {
      // Always render, even if theme fetch failed
      this.render();
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
    try {
      console.log('[AmplifyChat] render() called');

      // Create root if it doesn't exist
      if (!this.root) {
        console.log('[AmplifyChat] Creating React root...');
        this.root = createRoot(this);
        console.log('[AmplifyChat] React root created');
      }

      // Build props from attributes
      // Priority: attributes > runtime fetched > embedded build config > defaults
      const themePreset = super.getAttribute('theme-preset') ||
                         this.fetchedTheme?.themePreset ||
                         THEME_CONFIG.themePreset ||
                         'light';
      const themeOverrides = this.getThemeOverrides() ||
                            this.fetchedTheme?.themeOverrides ||
                            THEME_CONFIG.themeOverrides ||
                            undefined;

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
        themePreset: themePreset as 'light' | 'dark' | 'brand',
        themeOverrides: themeOverrides,
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

      console.log('[AmplifyChat] Rendering with props:', props);

      // Render the component
      this.root.render(
        React.createElement(ChatWithSources, props)
      );

      console.log('[AmplifyChat] React.createElement() completed');
    } catch (error) {
      console.error('[AmplifyChat] Error in render():', error);
      // Display error in the element
      this.innerHTML = `
        <div style="padding: 20px; border: 2px solid red; background: #fee; color: #c00;">
          <h3>AmplifyChat Error</h3>
          <p>Failed to render chat component. Check console for details.</p>
          <pre>${error instanceof Error ? error.message : String(error)}</pre>
        </div>
      `;
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
if (!customElements.get('amplify-chat')) {
  customElements.define('amplify-chat', AmplifyChat);
}

export { AmplifyChat };
