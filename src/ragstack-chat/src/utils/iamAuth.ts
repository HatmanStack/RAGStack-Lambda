/**
 * Lightweight IAM authentication for AppSync using Cognito Identity Pool
 *
 * This module provides unauthenticated access to AppSync via IAM credentials
 * obtained from Cognito Identity Pool. No AWS SDK required.
 */

interface CognitoCredentials {
  accessKeyId: string;
  secretAccessKey: string;
  sessionToken: string;
  expiration: number;
}

interface SignedRequest {
  headers: Record<string, string>;
}

// Cache credentials per identity pool to avoid fetching on every request
const credentialsCache = new Map<string, CognitoCredentials>();

/**
 * Get temporary AWS credentials from Cognito Identity Pool
 */
async function getCredentials(
  identityPoolId: string,
  region: string
): Promise<CognitoCredentials | null> {
  // Return cached credentials if still valid (with 5 min buffer)
  const cached = credentialsCache.get(identityPoolId);
  if (cached && cached.expiration > Date.now() + 300000) {
    return cached;
  }

  try {
    // Step 1: Get Identity ID
    const getIdResponse = await fetch(
      `https://cognito-identity.${region}.amazonaws.com/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityService.GetId',
        },
        body: JSON.stringify({
          IdentityPoolId: identityPoolId,
        }),
      }
    );

    if (!getIdResponse.ok) {
      console.error('[IAM Auth] Failed to get identity ID');
      return null;
    }

    const { IdentityId } = await getIdResponse.json();

    // Step 2: Get credentials for the identity
    const getCredentialsResponse = await fetch(
      `https://cognito-identity.${region}.amazonaws.com/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': 'AWSCognitoIdentityService.GetCredentialsForIdentity',
        },
        body: JSON.stringify({
          IdentityId,
        }),
      }
    );

    if (!getCredentialsResponse.ok) {
      console.error('[IAM Auth] Failed to get credentials');
      return null;
    }

    const { Credentials } = await getCredentialsResponse.json();

    const credentials: CognitoCredentials = {
      accessKeyId: Credentials.AccessKeyId,
      secretAccessKey: Credentials.SecretKey,
      sessionToken: Credentials.SessionToken,
      expiration: Credentials.Expiration * 1000, // Convert to ms
    };

    credentialsCache.set(identityPoolId, credentials);
    return credentials;
  } catch (error) {
    console.error('[IAM Auth] Error getting credentials:', error);
    return null;
  }
}

/**
 * Sign a request using AWS Signature Version 4
 * Simplified implementation for AppSync GraphQL requests
 */
async function signRequest(
  url: string,
  method: string,
  body: string,
  credentials: CognitoCredentials,
  region: string
): Promise<SignedRequest> {
  const urlObj = new URL(url);
  const host = urlObj.host;
  const path = urlObj.pathname || '/';
  const datetime = new Date().toISOString().replace(/[:-]|\.\d{3}/g, '');
  const date = datetime.slice(0, 8);

  // Create canonical request
  const hashedPayload = await sha256(body);
  const canonicalHeaders = [
    `content-type:application/json`,
    `host:${host}`,
    `x-amz-date:${datetime}`,
    `x-amz-security-token:${credentials.sessionToken}`,
  ].join('\n');
  const signedHeaders = 'content-type;host;x-amz-date;x-amz-security-token';

  const canonicalRequest = [
    method,
    path,
    '',
    canonicalHeaders,
    '',
    signedHeaders,
    hashedPayload,
  ].join('\n');

  // Create string to sign
  const credentialScope = `${date}/${region}/appsync/aws4_request`;
  const hashedCanonicalRequest = await sha256(canonicalRequest);
  const stringToSign = [
    'AWS4-HMAC-SHA256',
    datetime,
    credentialScope,
    hashedCanonicalRequest,
  ].join('\n');

  // Calculate signature
  const kDate = await hmacSha256(`AWS4${credentials.secretAccessKey}`, date);
  const kRegion = await hmacSha256(kDate, region);
  const kService = await hmacSha256(kRegion, 'appsync');
  const kSigning = await hmacSha256(kService, 'aws4_request');
  const signature = await hmacSha256Hex(kSigning, stringToSign);

  // Build authorization header
  const authorization = [
    `AWS4-HMAC-SHA256 Credential=${credentials.accessKeyId}/${credentialScope}`,
    `SignedHeaders=${signedHeaders}`,
    `Signature=${signature}`,
  ].join(', ');

  return {
    headers: {
      'Content-Type': 'application/json',
      'X-Amz-Date': datetime,
      'X-Amz-Security-Token': credentials.sessionToken,
      Authorization: authorization,
    },
  };
}

// Crypto helper functions using Web Crypto API
async function sha256(message: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(message);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

async function hmacSha256(
  key: string | ArrayBuffer,
  message: string
): Promise<ArrayBuffer> {
  const encoder = new TextEncoder();
  const keyData = typeof key === 'string' ? encoder.encode(key) : key;
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  return crypto.subtle.sign('HMAC', cryptoKey, encoder.encode(message));
}

async function hmacSha256Hex(
  key: ArrayBuffer,
  message: string
): Promise<string> {
  const signature = await hmacSha256(key, message);
  return Array.from(new Uint8Array(signature))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Make an IAM-authenticated request to AppSync
 */
export async function iamFetch(
  url: string,
  body: string,
  identityPoolId: string,
  region: string,
  signal?: AbortSignal
): Promise<Response> {
  const credentials = await getCredentials(identityPoolId, region);

  if (!credentials) {
    throw new Error('Failed to obtain IAM credentials');
  }

  const { headers } = await signRequest(url, 'POST', body, credentials, region);

  return fetch(url, {
    method: 'POST',
    headers,
    body,
    signal,
  });
}
