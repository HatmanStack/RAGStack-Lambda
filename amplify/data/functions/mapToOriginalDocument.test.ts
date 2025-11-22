/**
 * Unit tests for mapToOriginalDocument utility
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { mockClient } from 'aws-sdk-client-mock';
import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { mapToOriginalDocument } from './mapToOriginalDocument';
import { createMockChatConfig } from './types';

// Mock the presigner module
vi.mock('@aws-sdk/s3-request-presigner', () => ({
  getSignedUrl: vi.fn().mockResolvedValue('https://s3.amazonaws.com/bucket/key?presigned-params'),
}));

const dynamoMock = mockClient(DynamoDBClient);
const s3Mock = mockClient(S3Client);

describe('mapToOriginalDocument', () => {
  beforeEach(() => {
    dynamoMock.reset();
    s3Mock.reset();
    process.env.TRACKING_TABLE_NAME = 'test-tracking-table';
    process.env.AWS_REGION = 'us-east-1';
  });

  it('should return null when access is disabled', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: false });
    const result = await mapToOriginalDocument('s3://output-bucket/abc-123-def/chunks/chunk-001.json', config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });

  it('should extract document_id from citation URI', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: '12345678-1234-1234-1234-123456789abc' },
        input_s3_uri: { S: 's3://input-bucket/12345678-1234-1234-1234-123456789abc/document.pdf' },
        filename: { S: 'document.pdf' },
      },
    });

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeTruthy();
    expect(result.filename).toBe('document.pdf');
  });

  it('should generate presigned URL when access enabled', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/chunks/chunk-005.json';

    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee' },
        input_s3_uri: { S: 's3://my-bucket/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/report.pdf' },
        filename: { S: 'report.pdf' },
      },
    });

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBe('https://s3.amazonaws.com/bucket/key?presigned-params');
    expect(result.filename).toBe('report.pdf');
  });

  it('should handle missing documents gracefully', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/99999999-9999-9999-9999-999999999999/chunks/chunk-001.json';

    // Mock DynamoDB to return no item
    dynamoMock.on(GetItemCommand).resolves({
      Item: undefined,
    });

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });

  it('should handle invalid citation URI format', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const invalidUri = 's3://output-bucket/not-a-uuid/chunks/chunk-001.json';

    const result = await mapToOriginalDocument(invalidUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });

  it('should handle DynamoDB errors gracefully', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    // Mock DynamoDB to throw error
    dynamoMock.on(GetItemCommand).rejects(new Error('DynamoDB error'));

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });

  it('should handle invalid S3 URI format from TrackingTable', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: '12345678-1234-1234-1234-123456789abc' },
        input_s3_uri: { S: 'invalid-uri-format' },
        filename: { S: 'document.pdf' },
      },
    });

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('document.pdf');
  });

  it('should handle missing TRACKING_TABLE_NAME env var', async () => {
    delete process.env.TRACKING_TABLE_NAME;

    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });

  it('should handle missing filename in TrackingTable', async () => {
    const config = createMockChatConfig({ allowDocumentAccess: true });
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: '12345678-1234-1234-1234-123456789abc' },
        input_s3_uri: { S: 's3://bucket/key' },
        // filename missing
      },
    });

    const result = await mapToOriginalDocument(citationUri, config);

    expect(result.documentUrl).toBeNull();
    expect(result.filename).toBe('Unknown Document');
  });
});
