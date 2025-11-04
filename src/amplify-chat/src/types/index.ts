/**
 * Type definitions for Amplify Chat Component
 */

/**
 * Represents a single source/citation from the knowledge base
 */
export interface Source {
  title: string;
  location: string;
  snippet: string;
}

/**
 * Represents a single message in the conversation
 */
export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  timestamp: string;
  /** Model used to generate response (for quota tracking) */
  modelUsed?: string;
}

/**
 * Props for the ChatWithSources component
 */
export interface ChatWithSourcesProps {
  /**
   * Conversation ID - used to maintain separate conversation threads
   * @default "default"
   */
  conversationId?: string;

  /**
   * Custom CSS class to apply to the container
   * @default undefined
   */
  className?: string;

  /**
   * Custom header text
   * @default "Document Q&A"
   */
  headerText?: string;

  /**
   * Custom header subtitle
   * @default "Ask questions about your documents"
   */
  headerSubtitle?: string;

  /**
   * Custom placeholder for input field
   * @default "Ask a question..."
   */
  inputPlaceholder?: string;

  /**
   * Callback when message is sent (for tracking/analytics)
   * @param message - The message that was sent
   * @param conversationId - The conversation ID
   */
  onSendMessage?: (message: string, conversationId: string) => void;

  /**
   * Callback when response is received
   * @param response - The full response object with sources
   */
  onResponseReceived?: (response: ChatMessage) => void;

  /**
   * Show/hide sources section
   * @default true
   */
  showSources?: boolean;

  /**
   * Maximum width of the component
   * @default "100%"
   */
  maxWidth?: string;

  /**
   * User ID for authenticated mode (optional)
   * Phase 4 will use this for auth
   */
  userId?: string | null;

  /**
   * Authentication token for authenticated mode (optional)
   * Phase 4 will use this for auth
   */
  userToken?: string | null;

  /**
   * Theme preset (from configuration)
   * @default "light"
   */
  themePreset?: 'light' | 'dark' | 'brand';

  /**
   * Theme overrides (from configuration)
   */
  themeOverrides?: {
    primaryColor?: string;
    fontFamily?: string;
    spacing?: 'compact' | 'comfortable' | 'spacious';
  };
}

/**
 * Props for the SourcesDisplay component
 */
export interface SourcesDisplayProps {
  sources: Source[];
  /**
   * Custom CSS class
   */
  className?: string;
}

/**
 * Bedrock citation object (internal type)
 */
export interface BedrockCitation {
  title?: string;
  location?: {
    characterOffsets?: Array<{ start: number; end: number }>;
    pageNumber?: number;
  };
  sourceContent?: Array<{
    text?: string;
  }>;
}
