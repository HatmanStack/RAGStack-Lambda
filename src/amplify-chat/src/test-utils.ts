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
let mockStorage: Map<string, string>;

export const mockSessionStorage = () => {
  // Create a shared storage Map that persists
  mockStorage = new Map<string, string>();

  const sessionStorageMock = {
    getItem: vi.fn((key: string) => {
      const value = mockStorage.get(key) || null;
      return value;
    }),
    setItem: vi.fn((key: string, value: string) => {
      mockStorage.set(key, value);
    }),
    removeItem: vi.fn((key: string) => {
      mockStorage.delete(key);
    }),
    clear: vi.fn(() => {
      mockStorage.clear();
    }),
    get length() {
      return mockStorage.size;
    },
    key: vi.fn((index: number) => Array.from(mockStorage.keys())[index] || null),
  };

  global.sessionStorage = sessionStorageMock as Storage;

  return sessionStorageMock;
};

/**
 * Cleanup test utilities
 * Call after each test to reset state
 */
export const cleanupTestUtils = () => {
  if (global.sessionStorage) {
    sessionStorage.clear();
  }
  // Clear all mock function call history
  vi.clearAllMocks();
};
