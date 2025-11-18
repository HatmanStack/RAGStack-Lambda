/**
 * Performance Benchmarks for Document Mapping
 *
 * Tests performance of document mapping from citations to original files.
 * Target: < 100ms per query (including all mappings)
 *
 * Run with:
 *   cd amplify && npm run bench
 *
 * Or with vitest directly:
 *   npx vitest bench
 */

import { describe, bench, beforeEach, vi } from 'vitest';
import { mockClient } from 'aws-sdk-client-mock';
import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';
import { S3Client } from '@aws-sdk/client-s3';
import { mapToOriginalDocument } from '../mapToOriginalDocument';

// Mock the presigner module
vi.mock('@aws-sdk/s3-request-presigner', () => ({
  getSignedUrl: vi.fn().mockResolvedValue('https://s3.amazonaws.com/bucket/key?presigned'),
}));

const dynamoMock = mockClient(DynamoDBClient);
const s3Mock = mockClient(S3Client);

describe('Document Mapping Performance', () => {
  beforeEach(() => {
    dynamoMock.reset();
    s3Mock.reset();
    process.env.TRACKING_TABLE_NAME = 'test-tracking-table';
    process.env.AWS_REGION = 'us-east-1';

    // Mock successful DynamoDB response
    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: '12345678-1234-1234-1234-123456789abc' },
        input_s3_uri: { S: 's3://bucket/12345678-1234-1234-1234-123456789abc/document.pdf' },
        filename: { S: 'document.pdf' },
      },
    });
  });

  bench('Map 1 citation to original document', async () => {
    const config = { allowDocumentAccess: true };
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    await mapToOriginalDocument(citationUri, config);
  });

  bench('Map 5 citations in parallel', async () => {
    const config = { allowDocumentAccess: true };
    const citations = Array.from({ length: 5 }, (_, i) =>
      `s3://output-bucket/12345678-1234-1234-1234-12345678${String(i).padStart(4, '0')}/chunks/chunk-001.json`
    );

    await Promise.all(citations.map(uri => mapToOriginalDocument(uri, config)));
  });

  bench('Map 10 citations in parallel', async () => {
    const config = { allowDocumentAccess: true };
    const citations = Array.from({ length: 10 }, (_, i) =>
      `s3://output-bucket/12345678-1234-1234-1234-12345678${String(i).padStart(4, '0')}/chunks/chunk-001.json`
    );

    await Promise.all(citations.map(uri => mapToOriginalDocument(uri, config)));
  });

  bench('Map with access disabled (should be fast - no DB query)', async () => {
    const config = { allowDocumentAccess: false };
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    await mapToOriginalDocument(citationUri, config);
  });
});

describe('DynamoDB Query Performance', () => {
  beforeEach(() => {
    dynamoMock.reset();
    process.env.TRACKING_TABLE_NAME = 'test-tracking-table';
    process.env.AWS_REGION = 'us-east-1';
  });

  bench('Single TrackingTable GetItem query', async () => {
    dynamoMock.on(GetItemCommand).resolves({
      Item: {
        document_id: { S: '12345678-1234-1234-1234-123456789abc' },
        input_s3_uri: { S: 's3://bucket/key' },
        filename: { S: 'document.pdf' },
      },
    });

    const config = { allowDocumentAccess: true };
    const citationUri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';

    await mapToOriginalDocument(citationUri, config);
  });

  bench('Handle missing document gracefully', async () => {
    dynamoMock.on(GetItemCommand).resolves({ Item: undefined });

    const config = { allowDocumentAccess: true };
    const citationUri = 's3://output-bucket/99999999-9999-9999-9999-999999999999/chunks/chunk-001.json';

    await mapToOriginalDocument(citationUri, config);
  });
});

describe('UUID Extraction Performance', () => {
  bench('Extract UUID from valid S3 URI (regex)', () => {
    const uri = 's3://output-bucket/12345678-1234-1234-1234-123456789abc/chunks/chunk-001.json';
    const match = uri.match(/\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\//i);
    const documentId = match ? match[1] : null;

    if (!documentId) throw new Error('Should extract UUID');
  });

  bench('Handle invalid URI gracefully', () => {
    const uri = 's3://output-bucket/not-a-uuid/chunks/chunk-001.json';
    const match = uri.match(/\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\//i);
    const documentId = match ? match[1] : null;

    // Should be null, not throw
    if (documentId) throw new Error('Should return null for invalid UUID');
  });
});

/**
 * Performance Targets (from Phase 3 plan):
 *
 * - Document mapping (all citations): < 100ms per query
 * - Single presigned URL generation: < 50ms
 * - TrackingTable GetItem query: < 20ms
 *
 * Run these benchmarks and verify results meet targets before deploying to production.
 *
 * Example output:
 * ✓ Map 1 citation:  45ms  (target: <100ms) ✓
 * ✓ Map 5 citations: 62ms  (parallel execution) ✓
 * ✓ Map 10 citations: 89ms (parallel execution) ✓
 */
