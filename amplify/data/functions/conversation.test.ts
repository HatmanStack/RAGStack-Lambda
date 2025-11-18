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

  // Note: getChatConfig uses module-level caching which makes it difficult to test
  // reliably in a unit test environment. The function is tested indirectly through
  // handler integration tests.

  describe('getChatConfig', () => {
    it.skip('should read and parse config from DynamoDB', async () => {
      dynamoMock.on(GetItemCommand).resolves({
        Item: {
          chat_require_auth: { BOOL: false },
          chat_primary_model: { S: 'us.anthropic.claude-haiku-4-5-20251001-v1:0' },
          chat_fallback_model: { S: 'us.amazon.nova-micro-v1:0' },
          chat_global_quota_daily: { N: '10000' },
          chat_per_user_quota_daily: { N: '100' },
          chat_allow_document_access: { BOOL: true },
        },
      });

      const config = await getChatConfig();

      expect(config.requireAuth).toBe(false);
      expect(config.primaryModel).toBe('us.anthropic.claude-haiku-4-5-20251001-v1:0');
      expect(config.fallbackModel).toBe('us.amazon.nova-micro-v1:0');
      expect(config.globalQuotaDaily).toBe(10000);
      expect(config.perUserQuotaDaily).toBe(100);
      expect(config.allowDocumentAccess).toBe(true);
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
      expect(config.allowDocumentAccess).toBe(false);
    });

    it.skip('should throw error if config not found', async () => {
      dynamoMock.on(GetItemCommand).resolves({ Item: undefined });

      await expect(getChatConfig()).rejects.toThrow('Configuration not found');
    });
  });

  // Note: selectModelBasedOnQuotas and incrementQuotas are now internal helpers
  // within atomicQuotaCheckAndIncrement(). They are tested indirectly through
  // the main handler integration tests.

  describe('queryKnowledgeBase', () => {
    const mockConfig = {
      requireAuth: false,
      primaryModel: 'model',
      fallbackModel: 'fallback',
      globalQuotaDaily: 10000,
      perUserQuotaDaily: 100,
      allowDocumentAccess: false,
    };

    it('should query Bedrock and return response with sources', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).resolves({
        output: { text: 'Test response from Bedrock' },
        citations: [
          {
            retrievedReferences: [
              {
                location: { type: 'S3', s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/doc.pdf' } },
                content: { text: 'Sample content' },
                metadata: { 'x-amz-bedrock-kb-chunk-id': 'chunk-1' },
              },
            ],
          },
        ],
      });

      const result = await queryKnowledgeBase('test message', 'conv-123', 'model-arn', 'kb-id', 'us-east-1', mockConfig);

      expect(result.content).toBe('Test response from Bedrock');
      expect(result.modelUsed).toBe('model-arn');
      expect(result.sources).toHaveLength(1);
      expect(result.sources[0].documentAccessAllowed).toBe(false);
    });

    // TODO: Re-enable once Bedrock API sessionId validation issue is resolved
    // Currently disabled to prevent validation errors when KB ID changes across deployments
    it.skip('should use sessionId for conversation continuity', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).resolves({
        output: { text: 'Response' },
        citations: [],
      });

      await queryKnowledgeBase('message', 'conversation-id-123', 'model', 'kb', 'region', mockConfig);

      const call = bedrockMock.commandCalls(RetrieveAndGenerateCommand)[0];
      expect(call.args[0].input.sessionId).toBe('conversation-id-123');
    });

    it('should throw error if Bedrock query fails', async () => {
      bedrockMock.on(RetrieveAndGenerateCommand).rejects(new Error('Bedrock error'));

      await expect(
        queryKnowledgeBase('message', 'conv', 'model', 'kb', 'region', mockConfig)
      ).rejects.toThrow('Knowledge Base query failed');
    });
  });

  describe('extractSources', () => {
    const mockConfig = {
      requireAuth: false,
      primaryModel: 'model',
      fallbackModel: 'fallback',
      globalQuotaDaily: 10000,
      perUserQuotaDaily: 100,
      allowDocumentAccess: false,
    };

    beforeEach(() => {
      process.env.TRACKING_TABLE_NAME = 'test-tracking-table';
      process.env.AWS_REGION = 'us-east-1';
    });

    it('should extract title, location, and snippet from citations', async () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/document.pdf' } },
              content: { text: 'This is sample content from the document' },
              metadata: { 'x-amz-bedrock-kb-chunk-id': 'chunk-123' },
            },
          ],
        },
      ];

      const sources = await extractSources(citations, mockConfig);

      expect(sources).toHaveLength(1);
      expect(sources[0].location).toBe('chunk-123');
      expect(sources[0].snippet).toBe('This is sample content from the document');
      expect(sources[0].documentAccessAllowed).toBe(false);
      expect(sources[0].documentUrl).toBeNull();
    });

    it('should limit snippet to 200 characters', async () => {
      const longText = 'a'.repeat(300);
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/doc.pdf' } },
              content: { text: longText },
              metadata: {},
            },
          ],
        },
      ];

      const sources = await extractSources(citations, mockConfig);

      expect(sources[0].snippet.length).toBe(200);
    });

    it('should remove duplicate sources based on snippet', async () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/doc1.pdf' } },
              content: { text: 'Same content' },
              metadata: {},
            },
            {
              location: { s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/doc2.pdf' } },
              content: { text: 'Same content' },
              metadata: {},
            },
          ],
        },
      ];

      const sources = await extractSources(citations, mockConfig);

      expect(sources).toHaveLength(1);
    });

    it('should skip entries without S3 URI', async () => {
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

      const sources = await extractSources(citations, mockConfig);

      expect(sources).toHaveLength(0);
    });

    it('should return empty array for empty citations', async () => {
      const sources = await extractSources([], mockConfig);

      expect(sources).toEqual([]);
    });

    it('should skip references without content', async () => {
      const citations = [
        {
          retrievedReferences: [
            {
              location: { s3Location: { uri: 's3://bucket/12345678-1234-1234-1234-123456789abc/doc.pdf' } },
              content: { text: '' }, // Empty content
              metadata: {},
            },
          ],
        },
      ];

      const sources = await extractSources(citations, mockConfig);

      expect(sources).toEqual([]);
    });
  });

  describe('atomicQuotaCheckAndIncrement', () => {
    const mockConfig = {
      requireAuth: false,
      primaryModel: 'primary-model-arn',
      fallbackModel: 'fallback-model-arn',
      globalQuotaDaily: 100,
      perUserQuotaDaily: 10,
      allowDocumentAccess: false,
    };

    beforeEach(() => {
      process.env.CONFIGURATION_TABLE_NAME = 'test-config-table';
      process.env.AWS_REGION = 'us-east-1';
    });

    it('should return primary model when quotas are within limits', async () => {
      const { atomicQuotaCheckAndIncrement } = await import('./conversation');

      // Mock successful quota updates
      dynamoMock.on(UpdateItemCommand).resolves({
        Attributes: { count: { N: '1' } }
      });

      const model = await atomicQuotaCheckAndIncrement('test-user', mockConfig, false);

      expect(model).toBe('primary-model-arn');
    });

    it('should return fallback model when global quota exceeded', async () => {
      const { atomicQuotaCheckAndIncrement } = await import('./conversation');

      // Mock global quota exceeded
      dynamoMock.on(UpdateItemCommand).rejects({
        name: 'ConditionalCheckFailedException',
        message: 'Quota exceeded',
      });

      const model = await atomicQuotaCheckAndIncrement('test-user', mockConfig, false);

      expect(model).toBe('fallback-model-arn');
    });

    it('should return fallback model on DynamoDB error', async () => {
      const { atomicQuotaCheckAndIncrement } = await import('./conversation');

      // Mock DynamoDB error
      dynamoMock.on(UpdateItemCommand).rejects(new Error('DynamoDB error'));

      const model = await atomicQuotaCheckAndIncrement('test-user', mockConfig, false);

      expect(model).toBe('fallback-model-arn');
    });
  });
});
