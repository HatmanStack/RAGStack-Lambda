/**
 * Test Utilities
 *
 * Common mocks and helpers for component testing
 */

import { vi } from 'vitest';

/**
 * Mock scrollIntoView for auto-scroll tests
 * MessageList component uses this for auto-scrolling to bottom
 */
export const mockScrollIntoView = () => {
  window.HTMLElement.prototype.scrollIntoView = vi.fn();
};

/**
 * Mock sessionStorage for persistence tests
 * ChatInterface component uses this for message persistence
 */
export const mockSessionStorage = () => {
  const storage = new Map<string, string>();

  global.sessionStorage = {
    getItem: (key: string) => storage.get(key) || null,
    setItem: (key: string, value: string) => storage.set(key, value),
    removeItem: (key: string) => storage.delete(key),
    clear: () => storage.clear(),
    length: storage.size,
    key: (index: number) => Array.from(storage.keys())[index] || null,
  } as Storage;
};

/**
 * Cleanup test utilities
 * Call after each test to reset state
 */
export const cleanupTestUtils = () => {
  if (global.sessionStorage) {
    sessionStorage.clear();
  }
};
