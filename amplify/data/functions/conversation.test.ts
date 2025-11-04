/**
 * Unit tests for conversation handler
 *
 * NOTE: These tests require dev dependencies:
 *   npm install --save-dev vitest aws-sdk-client-mock @aws-sdk/client-dynamodb @aws-sdk/client-bedrock-agent-runtime
 *
 * Run with: npm test
 */
import { describe, it, expect, beforeEach } from 'vitest';
import { mockClient } from 'aws-sdk-client-mock';
import { DynamoDBClient, GetItemCommand, UpdateItemCommand } from '@aws-sdk/client-dynamodb';
import { BedrockAgentRuntimeClient, RetrieveAndGenerateCommand } from '@aws-sdk/client-bedrock-agent-runtime';
import {
  getChatConfig,
  queryKnowledgeBase,
  extractSources,
} from './conversation';

const dynamoMock = mockClient(DynamoDBClient);
const bedrockMock = mockClient(BedrockAgentRuntimeClient);

describe('Conversation Handler', () => {
  beforeEach(() => {
    dynamoMock.reset();
    bedrockMock.reset();
  });

  describe('getChatConfig', () => {
    it('should read and parse config from DynamoDB', async () => {
      dynamoMock.on(GetItemCommand).resolves({
        Item: {
          chat_require_auth: { BOOL: false },
          chat_primary_model: { S: 'us.anthropic.claude-haiku-4-5-20251001-v1:0' },
          chat_fallback_model: { S: 'us.amazon.nova-micro-v1:0' },
          chat_global_quota_daily: { N: '10000' },
          chat_per_user_quota_daily: { N: '100' },
        },
      });

      const config = await freshGetChatConfig();

      expect(config.requireAuth).toBe(false);
      expect(config.primaryModel).toBe('us.anthropic.claude-haiku-4-5-20251001-v1:0');
      expect(config.fallbackModel).toBe('us.amazon.nova-micro-v1:0');
      expect(config.globalQuotaDaily).toBe(10000);
      expect(config.perUserQuotaDaily).toBe(100);
    });

    it('should use default values for missing config fields', async () => {
      dynamoMock.on(GetItemCommand).resolves({
        Item: {}, // Empty config but item exists
      });

      const config = await getChatConfig();

      expect(config.requireAuth).toBe(false);
      expect(config.primaryModel).toBe('us.anthropic.claude-haiku-4-5-20251001-v1:0');
      expect(config.fallbackModel).toBe('us.amazon.nova-micro-v1:0');
      expect(config.globalQuotaDaily).toBe(10000);
      expect(config.perUserQuotaDaily).toBe(100);
    });
  });

  // Note: selectModelBasedOnQuotas and incrementQuotas are now internal helpers
  // within atomicQuotaCheckAndIncrement(). They are tested indirectly through
  // the main handler integration tests.

  describe('queryKnowledgeBase', () => {
    it('should query Bedrock and return response with sources', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).resolves({
        output: { text: 'Test response from Bedrock' },
        citations: [
          {
            retrievedReferences: [
              {
                location: { s3Location: { uri: 's3://bucket/doc.pdf' } },
                content: { text: 'Sample content' },
                metadata: { 'x-amz-bedrock-kb-chunk-id': 'chunk-1' },
              },
            ],
          },
        ],
      });

      const result = await queryKnowledgeBase('test message', 'conv-123', 'model-arn', 'kb-id', 'us-east-1');

      expect(result.content).toBe('Test response from Bedrock');
      expect(result.modelUsed).toBe('model-arn');
      expect(result.sources).toHaveLength(1);
      expect(result.sources[0].title).toBe('doc.pdf');
    });

    it('should use sessionId for conversation continuity', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).resolves({
        output: { text: 'Response' },
        citations: [],
      });

      await queryKnowledgeBase('message', 'conversation-id-123', 'model', 'kb', 'region');

      const call = bedrockMock.commandCalls(RetrieveAndGenerateCommand)[0];
      expect(call.args[0].input.sessionId).toBe('conversation-id-123');
    });

    it('should throw error if Bedrock query fails', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).rejects(new Error('Bedrock error'));

      await expect(
        queryKnowledgeBase('message', 'conv', 'model', 'kb', 'region')
      ).rejects.toThrow('Knowledge Base query failed');
    });
  });

  describe('extractSources', () => {
    it('should extract title, location, and snippet from citations', () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/document.pdf' } },
              content: { text: 'This is sample content from the document' },
              metadata: { 'x-amz-bedrock-kb-chunk-id': 'chunk-123' },
            },
          ],
        },
      ];

      const sources = extractSources(citations);

      expect(sources).toHaveLength(1);
      expect(sources[0].title).toBe('document.pdf');
      expect(sources[0].location).toBe('chunk-123');
      expect(sources[0].snippet).toBe('This is sample content from the document');
    });

    it('should limit snippet to 200 characters', () => {
      const longText = 'a'.repeat(300);
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/doc.pdf' } },
              content: { text: longText },
              metadata: {},
            },
          ],
        },
      ];

      const sources = extractSources(citations);

      expect(sources[0].snippet.length).toBe(200);
    });

    it('should remove duplicate sources based on snippet', () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/doc1.pdf' } },
              content: { text: 'Same content' },
              metadata: {},
            },
            {
              location: { s3Location: { uri: 's3://bucket/doc2.pdf' } },
              content: { text: 'Same content' },
              metadata: {},
            },
          ],
        },
      ];

      const sources = extractSources(citations);

      expect(sources).toHaveLength(1);
    });

    it('should handle missing S3 URI gracefully', () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: {},
              content: { text: 'Content without S3 URI' },
              metadata: {},
            },
          ],
        },
      ];

      const sources = extractSources(citations);

      expect(sources[0].title).toBe('Unknown Document');
    });

    it('should return empty array for empty citations', () => {
      const sources = extractSources([]);

      expect(sources).toEqual([]);
    });

    it('should skip references without content', () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/doc.pdf' } },
              content: { text: '' }, // Empty content
              metadata: {},
            },
          ],
        },
      ];

      const sources = extractSources(citations);

      expect(sources).toEqual([]);
    });
  });
});
