/**
 * Conversation ID Utilities
 *
 * Generates and manages unique conversation IDs for chat sessions.
 * IDs are persisted in localStorage to maintain conversation continuity
 * across page reloads while ensuring isolation between users/browsers.
 */

const STORAGE_KEY = 'ragstack-conversation-id';
const UUID_V4_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

/**
 * Check if a string is a valid UUID v4 format.
 * Validates version nibble (4) and variant bits (8/9/a/b).
 * Exported as isValidConversationId for use by components.
 */
function isValidUUID(id: string): boolean {
  return UUID_V4_REGEX.test(id);
}

export const isValidConversationId = isValidUUID;

/**
 * Generate a UUID v4 string.
 * Uses crypto.randomUUID if available, falls back to manual generation.
 */
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Get or create a unique conversation ID for this browser.
 *
 * - Checks localStorage for existing ID
 * - If not found, generates a new UUID and persists it
 * - Returns the ID for use in chat sessions
 *
 * This ensures each browser/user has their own isolated conversation
 * history, even for anonymous/public chat access.
 *
 * @returns Unique conversation ID string
 */
export function getOrCreateConversationId(): string {
  // Check if we're in a browser environment
  if (typeof window === 'undefined' || typeof localStorage === 'undefined') {
    // Server-side or no localStorage - generate a temporary ID
    return generateUUID();
  }

  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id || !isValidUUID(id)) {
      id = generateUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    // localStorage might be blocked (private browsing, etc.)
    // Fall back to a session-only ID
    return generateUUID();
  }
}

/**
 * Clear the stored conversation ID.
 * Useful for "start new conversation" functionality.
 */
export function clearConversationId(): void {
  if (typeof localStorage !== 'undefined') {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignore errors
    }
  }
}

/**
 * Generate a new conversation ID and store it.
 * Useful for explicitly starting a fresh conversation.
 *
 * @returns The new conversation ID
 */
export function resetConversationId(): string {
  const newId = generateUUID();
  if (typeof localStorage !== 'undefined') {
    try {
      localStorage.setItem(STORAGE_KEY, newId);
    } catch {
      // Ignore errors
    }
  }
  return newId;
}
