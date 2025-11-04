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
  selectModelBasedOnQuotas,
  incrementQuotas,
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

  describe('selectModelBasedOnQuotas', () => {
    const mockConfig = {
      requireAuth: false,
      primaryModel: 'primary-model',
      fallbackModel: 'fallback-model',
      globalQuotaDaily: 100,
      perUserQuotaDaily: 10,
    };

    it('should select primary model when within global quota', async () => {
      dynamoMock.on(GetItemCommand).resolves({
        Item: { count: { N: '50' } }, // Under global limit
      });

      const model = await selectModelBasedOnQuotas('test-user', mockConfig, false);

      expect(model).toBe('primary-model');
    });

    it('should select fallback model when global quota exceeded', async () => {
      dynamoMock.on(GetItemCommand).resolves({
        Item: { count: { N: '101' } }, // Over global limit
      });

      const model = await selectModelBasedOnQuotas('test-user', mockConfig, false);

      expect(model).toBe('fallback-model');
    });

    it('should select primary model when within both quotas (authenticated)', async () => {
      // Mock needs to handle multiple GetItemCommand calls with different keys
      let callCount = 0;
      dynamoMock.on(GetItemCommand).callsFake((input) => {
        callCount++;
        const key = input.Key?.Configuration?.S || '';

        if (key.includes('quota#global#')) {
          return { Item: { count: { N: '50' } } }; // Global: under limit
        } else if (key.includes('quota#user#')) {
          return { Item: { count: { N: '5' } } }; // User: under limit
        }
        return {}; // Quota doesn't exist yet
      });

      const model = await selectModelBasedOnQuotas('test-user', mockConfig, true);

      expect(model).toBe('primary-model');
    });

    it('should select fallback model when user quota exceeded (authenticated)', async () => {
      dynamoMock
        .on(GetItemCommand, { TableName: expect.anything(), Key: { Configuration: { S: expect.stringContaining('quota#global#') } } })
        .resolves({ Item: { count: { N: '50' } } }) // Global: under limit
        .on(GetItemCommand, { TableName: expect.anything(), Key: { Configuration: { S: expect.stringContaining('quota#user#') } } })
        .resolves({ Item: { count: { N: '11' } } }); // User: over limit

      const model = await selectModelBasedOnQuotas('test-user', mockConfig, true);

      expect(model).toBe('fallback-model');
    });

    it('should select fallback model on DynamoDB error (conservative approach)', async () => {
      dynamoMock.on(GetItemCommand).rejects(new Error('DynamoDB error'));

      const model = await selectModelBasedOnQuotas('test-user', mockConfig, false);

      expect(model).toBe('fallback-model');
    });
  });

  describe('incrementQuotas', () => {
    it('should increment global quota for anonymous users', async () => {
      dynamoMock.on(UpdateItemCommand).resolves({});

      await incrementQuotas('anon:conversation-123', false);

      expect(dynamoMock.commandCalls(UpdateItemCommand).length).toBe(1);
      const call = dynamoMock.commandCalls(UpdateItemCommand)[0];
      expect(call.args[0].input.Key?.Configuration.S).toContain('quota#global#');
      expect(call.args[0].input.UpdateExpression).toContain('ADD #count :inc');
    });

    it('should increment both global and user quota for authenticated users', async () => {
      dynamoMock.on(UpdateItemCommand).resolves({});

      await incrementQuotas('test-user', true);

      expect(dynamoMock.commandCalls(UpdateItemCommand).length).toBe(2);
      const calls = dynamoMock.commandCalls(UpdateItemCommand);
      expect(calls[0].args[0].input.Key?.Configuration.S).toContain('quota#global#');
      expect(calls[1].args[0].input.Key?.Configuration.S).toContain('quota#user#test-user#');
    });

    it('should set TTL to 2 days from now', async () => {
      dynamoMock.on(UpdateItemCommand).resolves({});

      const beforeTime = Math.floor(Date.now() / 1000) + (86400 * 2);
      await incrementQuotas('test-user', false);
      const afterTime = Math.floor(Date.now() / 1000) + (86400 * 2);

      const call = dynamoMock.commandCalls(UpdateItemCommand)[0];
      const ttl = parseInt(call.args[0].input.ExpressionAttributeValues?.[':ttl'].N || '0');
      expect(ttl).toBeGreaterThanOrEqual(beforeTime);
      expect(ttl).toBeLessThanOrEqual(afterTime);
    });

    it('should not throw error if DynamoDB fails (non-fatal)', async () => {
      dynamoMock.on(UpdateItemCommand).rejects(new Error('DynamoDB error'));

      await expect(incrementQuotas('test-user', false)).resolves.not.toThrow();
    });
  });

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
