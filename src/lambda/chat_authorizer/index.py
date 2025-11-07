"""
Lambda Authorizer for AppSync GraphQL API

Validates Cognito JWT tokens and supports optional anonymous access
based on runtime configuration from ConfigurationTable.

Flow:
1. Check ConfigurationTable for chat_require_auth setting
2. If auth not required and no token provided, allow anonymous access
3. If token provided, validate against Cognito User Pool
4. If auth required and no valid token, deny access
"""

import os
import json
import time
import boto3
from jose import jwt, JWTError
from jose.backends import RSAKey
from urllib.request import urlopen
from functools import lru_cache

# Environment variables
USER_POOL_ID = os.environ['USER_POOL_ID']
USER_POOL_CLIENT_ID = os.environ['USER_POOL_CLIENT_ID']
REGION = os.environ['AWS_REGION']
CONFIGURATION_TABLE = os.environ['CONFIGURATION_TABLE_NAME']

# DynamoDB client
dynamodb = boto3.client('dynamodb')

# Cache for Cognito JWKS (reuse across invocations)
_jwks_cache = None
_jwks_cache_time = 0
JWKS_CACHE_TTL = 3600  # 1 hour

# Cache for auth config (reuse across invocations)
_auth_required_cache = None
_auth_cache_time = 0
AUTH_CACHE_TTL = 60  # 60 seconds


@lru_cache(maxsize=1)
def get_jwks_url():
    """Get Cognito JWKS URL"""
    return f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json'


def get_jwks():
    """Fetch and cache Cognito JWKS"""
    global _jwks_cache, _jwks_cache_time

    now = time.time()
    if _jwks_cache and (now - _jwks_cache_time < JWKS_CACHE_TTL):
        return _jwks_cache

    print(f'Fetching JWKS from {get_jwks_url()}')
    with urlopen(get_jwks_url()) as response:
        jwks = json.loads(response.read())
        _jwks_cache = jwks
        _jwks_cache_time = now
        return jwks


def get_auth_required():
    """
    Check ConfigurationTable to see if authentication is required.
    Returns True if auth is required, False if anonymous access is allowed.
    """
    global _auth_required_cache, _auth_cache_time

    now = time.time()
    if _auth_required_cache is not None and (now - _auth_cache_time < AUTH_CACHE_TTL):
        print(f'Using cached auth config: {_auth_required_cache}')
        return _auth_required_cache

    print('Fetching auth config from DynamoDB...')
    try:
        response = dynamodb.get_item(
            TableName=CONFIGURATION_TABLE,
            Key={'Configuration': {'S': 'Default'}}
        )

        if 'Item' not in response:
            print('Configuration not found, defaulting to auth required')
            return True  # Fail secure

        # Parse requireAuth setting (default to False for backwards compatibility)
        require_auth = response['Item'].get('chat_require_auth', {}).get('BOOL', False)

        # Update cache
        _auth_required_cache = require_auth
        _auth_cache_time = now

        print(f'Auth config loaded: requireAuth={require_auth}')
        return require_auth

    except Exception as e:
        print(f'Error fetching config: {e}')
        # Fail secure - require auth if we can't read config
        return True


def verify_token(token):
    """
    Verify JWT token against Cognito User Pool
    Returns payload if valid, raises exception if invalid
    """
    # Get JWKS
    jwks = get_jwks()

    # Decode header to get kid
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header['kid']

    # Find the correct key
    key = None
    for jwk in jwks['keys']:
        if jwk['kid'] == kid:
            key = jwk
            break

    if not key:
        raise JWTError(f'Public key not found for kid: {kid}')

    # Verify token
    payload = jwt.decode(
        token,
        key,
        algorithms=['RS256'],
        audience=USER_POOL_CLIENT_ID,
        issuer=f'https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}'
    )

    return payload


def lambda_handler(event, context):
    """
    Lambda Authorizer Handler

    Args:
        event: AppSync authorization event with authorizationToken
        context: Lambda context

    Returns:
        Authorization response with isAuthorized and resolverContext
    """
    print('Authorization request received')

    # Check if authentication is required
    require_auth = get_auth_required()

    # Extract token from Authorization header
    auth_token = event.get('authorizationToken', '')
    token = auth_token.replace('Bearer ', '').strip() if auth_token else None

    if not token:
        print('No authorization token provided')

        # If auth is not required, allow anonymous access
        if not require_auth:
            print('Auth not required, allowing anonymous access')
            return {
                'isAuthorized': True,
                'resolverContext': {
                    'userId': 'anonymous',
                    'isAnonymous': 'true'
                },
                'deniedFields': [],
                'ttlOverride': 300  # Cache for 5 minutes
            }

        # Auth is required but no token provided - deny
        print('Auth required but no token provided')
        return {
            'isAuthorized': False,
            'resolverContext': {},
            'deniedFields': [],
            'ttlOverride': 0
        }

    # Token provided - validate it
    try:
        payload = verify_token(token)

        print(f'Token verified successfully: userId={payload.get("sub")}')

        return {
            'isAuthorized': True,
            'resolverContext': {
                'userId': payload.get('sub', 'unknown'),
                'username': payload.get('cognito:username', 'unknown'),
                'email': payload.get('email', ''),
                'isAnonymous': 'false'
            },
            'deniedFields': [],
            'ttlOverride': 300  # Cache for 5 minutes
        }

    except JWTError as e:
        print(f'Token verification failed: {str(e)}')
        return {
            'isAuthorized': False,
            'resolverContext': {},
            'deniedFields': [],
            'ttlOverride': 0
        }
    except Exception as e:
        print(f'Unexpected error during authorization: {str(e)}')
        return {
            'isAuthorized': False,
            'resolverContext': {},
            'deniedFields': [],
            'ttlOverride': 0
        }
