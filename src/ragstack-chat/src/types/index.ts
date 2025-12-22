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
  /** Presigned URL for downloading the original document (optional) */
  documentUrl?: string | null;
  /** Whether document access is allowed by admin configuration (optional) */
  documentAccessAllowed?: boolean;
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
    backgroundColor?: string;
    textColor?: string;
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

/**
 * Props for the ChatInterface component
 * Main chat component that manages message state
 */
export interface ChatInterfaceProps {
  /**
   * Conversation ID - used for session persistence
   */
  conversationId: string;

  /**
   * User ID for authenticated mode (optional)
   */
  userId?: string | null;

  /**
   * Authentication token for authenticated mode (optional)
   */
  userToken?: string | null;

  /**
   * Callback when message is sent
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
   * Input placeholder text
   * @default "Type your message..."
   */
  inputPlaceholder?: string;
}

/**
 * Error state for MessageList component
 */
export interface ErrorState {
  type: 'auth' | 'quota' | 'network' | 'validation' | 'unknown';
  message: string;
  retryable: boolean;
  onRetry?: () => void;
  /** Number of retry attempts made (for rate limiting) */
  retryCount?: number;
}

/**
 * Props for the MessageList component
 * Scrollable container for messages
 */
export interface MessageListProps {
  /**
   * Array of messages to display
   */
  messages: ChatMessage[];

  /**
   * Loading indicator state
   */
  isLoading: boolean;

  /**
   * Error state (if any)
   */
  error?: ErrorState | null;

  /**
   * Show/hide sources section
   * @default true
   */
  showSources?: boolean;
}

/**
 * Props for the MessageBubble component
 * Individual message display
 */
export interface MessageBubbleProps {
  /**
   * Message to display
   */
  message: ChatMessage;

  /**
   * Show/hide sources section
   * @default true
   */
  showSources?: boolean;
}

/**
 * Props for the MessageInput component
 * Text input with send button
 */
export interface MessageInputProps {
  /**
   * Callback when message is sent
   * @param message - The message text
   */
  onSend: (message: string) => void;

  /**
   * Loading state - disables input during send
   */
  isLoading: boolean;

  /**
   * Placeholder text
   * @default "Type your message..."
   */
  placeholder?: string;
}
