/**
 * Integration Tests for Conversation Flow
 *
 * These tests use the REAL deployed Amplify backend to verify
 * end-to-end functionality with actual GraphQL queries.
 *
 * Run with: npm run test -- integration
 */

import { describe, it, expect, beforeAll } from 'vitest';
import { Amplify } from 'aws-amplify';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '../../../../../amplify/data/resource';

// Load amplify_outputs configuration from project root
// Path explanation:
//   - From: src/amplify-chat/src/components/__tests__/integration/
//   - Up 4 levels to src/amplify-chat/: ../../../../
//   - Up 2 more levels to project root: ../../
//   - Total: ../../../../../../amplify_outputs.json
// NOTE: This could be improved with a tsconfig path alias if needed
import outputs from '../../../../../../amplify_outputs.json';

/**
 * Generate unique conversation ID to prevent test pollution
 * Each test run gets its own conversation to avoid interference
 */
const generateConversationId = () =>
  `integration-test-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`;

// TODO: Integration tests require backend to be deployed and accessible
// Currently skipped due to test environment configuration complexity
describe.skip('Integration: Conversation GraphQL Query', () => {
  let client: ReturnType<typeof generateClient<Schema>>;

  beforeAll(() => {
    // Configure Amplify with real backend
    Amplify.configure(outputs);
    client = generateClient<Schema>();
  });

  it('should successfully query the conversation endpoint', async () => {
    const result = await client.queries.conversation({
      message: 'What is the capital of France?',
      conversationId: generateConversationId(),
    });

    // Verify response structure
    expect(result.data).toBeDefined();
    if (result.data) {
      expect(result.data.content).toBeDefined();
      expect(typeof result.data.content).toBe('string');
      expect(result.data.content).not.toBe('');

      // Sources may or may not be present depending on KB content
      expect(result.data.sources).toBeDefined();
      expect(Array.isArray(result.data.sources)).toBe(true);

      // Model used should be specified
      expect(result.data.modelUsed).toBeDefined();
      expect(typeof result.data.modelUsed).toBe('string');
    }

    // Should not have errors
    expect(result.errors).toBeUndefined();
  }, 30000); // 30s timeout for real backend call

  it('should handle multiple messages in same conversation', async () => {
    // Use unique ID to prevent pollution between test runs
    const conversationId = generateConversationId();

    // First message
    const result1 = await client.queries.conversation({
      message: 'Hello',
      conversationId,
    });

    expect(result1.data?.content).toBeDefined();

    // Second message in same conversation
    const result2 = await client.queries.conversation({
      message: 'How are you?',
      conversationId,
    });

    expect(result2.data?.content).toBeDefined();

    // Both should succeed
    expect(result1.errors).toBeUndefined();
    expect(result2.errors).toBeUndefined();
  }, 60000); // 60s timeout for multiple calls

  it('should work in guest mode (no userId/userToken)', async () => {
    const result = await client.queries.conversation({
      message: 'Test guest mode',
      conversationId: generateConversationId(),
      // No userId or userToken provided
    });

    // Should still work in guest mode
    expect(result.data).toBeDefined();
    if (result.data) {
      expect(result.data.content).toBeDefined();
      expect(result.data.content).not.toBe('');
    }
  }, 30000);
});
