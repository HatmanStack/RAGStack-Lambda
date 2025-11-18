/**
 * Document URL Mapping Utility
 *
 * Maps Bedrock Knowledge Base citation S3 URIs to original documents in InputBucket.
 * Generates secure presigned URLs for document access when enabled.
 */

import { DynamoDBClient, GetItemCommand } from '@aws-sdk/client-dynamodb';
import { S3Client, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

interface ChatConfig {
  allowDocumentAccess: boolean;
  [key: string]: any;
}

interface DocumentMapping {
  documentUrl: string | null;
  filename: string;
}

/**
 * Maps a Bedrock citation S3 URI to the original document URL
 *
 * @param citationS3Uri - S3 URI from Bedrock citation (points to OutputBucket chunk)
 * @param config - Chat configuration including allowDocumentAccess flag
 * @returns Document URL (presigned) and filename, or null values if disabled/error
 */
export async function mapToOriginalDocument(
  citationS3Uri: string,
  config: ChatConfig
): Promise<DocumentMapping> {
  // Early return if document access is disabled
  if (!config.allowDocumentAccess) {
    console.log('Document access disabled, skipping URL generation');
    return { documentUrl: null, filename: 'Unknown Document' };
  }

  try {
    // Step 1: Extract document_id from citation URI
    // Citation format: s3://output-bucket/{document_id}/chunks/chunk-NNN.json
    const documentId = extractDocumentId(citationS3Uri);
    if (!documentId) {
      console.warn('Could not extract document_id from URI:', citationS3Uri);
      return { documentUrl: null, filename: 'Unknown Document' };
    }

    console.log('Extracted document_id:', documentId);

    // Step 2: Query TrackingTable for original document info
    const trackingData = await queryTrackingTable(documentId);
    if (!trackingData) {
      console.warn('Document not found in TrackingTable:', documentId);
      return { documentUrl: null, filename: 'Unknown Document' };
    }

    const { inputS3Uri, filename } = trackingData;

    // Step 3: Parse S3 URI to get bucket and key
    const s3Location = parseS3Uri(inputS3Uri);
    if (!s3Location) {
      console.warn('Invalid S3 URI format:', inputS3Uri);
      return { documentUrl: null, filename };
    }

    // Step 4: Generate presigned URL
    const documentUrl = await generatePresignedUrl(s3Location.bucket, s3Location.key);

    console.log('Presigned URL generated for document:', { documentId, filename });
    return { documentUrl, filename };

  } catch (error) {
    console.error('Error mapping document URL:', error);
    return { documentUrl: null, filename: 'Unknown Document' };
  }
}

/**
 * Extracts document_id (UUID) from citation S3 URI
 */
function extractDocumentId(s3Uri: string): string | null {
  // Match UUID pattern in S3 URI (8-4-4-4-12 hex digits)
  const match = s3Uri.match(/\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\//i);
  return match ? match[1] : null;
}

/**
 * Queries TrackingTable for original document information
 */
async function queryTrackingTable(documentId: string): Promise<{ inputS3Uri: string; filename: string } | null> {
  const tableName = process.env.TRACKING_TABLE_NAME;
  if (!tableName) {
    console.error('TRACKING_TABLE_NAME environment variable not set');
    return null;
  }

  const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION! });

  try {
    const result = await dynamodb.send(
      new GetItemCommand({
        TableName: tableName,
        Key: { document_id: { S: documentId } },
      })
    );

    if (!result.Item) {
      return null;
    }

    const inputS3Uri = result.Item.input_s3_uri?.S;
    const filename = result.Item.filename?.S;

    if (!inputS3Uri || !filename) {
      console.warn('Missing required fields in TrackingTable:', { documentId, inputS3Uri, filename });
      return null;
    }

    return { inputS3Uri, filename };

  } catch (error) {
    console.error('DynamoDB GetItem error:', error);
    return null;
  }
}

/**
 * Parses S3 URI into bucket and key components
 */
function parseS3Uri(s3Uri: string): { bucket: string; key: string } | null {
  // Match s3://bucket/key format
  const match = s3Uri.match(/^s3:\/\/([^/]+)\/(.+)$/);
  if (!match) {
    return null;
  }

  return {
    bucket: match[1],
    key: match[2],
  };
}

/**
 * Generates presigned URL for S3 object with 1-hour expiry
 */
async function generatePresignedUrl(bucket: string, key: string): Promise<string> {
  const s3Client = new S3Client({ region: process.env.AWS_REGION! });

  const command = new GetObjectCommand({
    Bucket: bucket,
    Key: key,
  });

  // Generate presigned URL with 1-hour (3600 seconds) expiry
  const presignedUrl = await getSignedUrl(s3Client, command, { expiresIn: 3600 });

  return presignedUrl;
}
