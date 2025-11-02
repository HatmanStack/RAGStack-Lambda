# Phase 3: Chat Backend - QueryKB Lambda Enhancement

## Overview

Enhance the existing QueryKB Lambda to support conversational chat by:
1. Adding optional `sessionId` parameter for conversation continuity
2. Reading `chat_model_id` dynamically from configuration table
3. Returning enhanced response with sessionId and structured sources
4. Updating GraphQL schema to support chat features

**Approach**: Leverage Bedrock's built-in session management instead of manual history tracking. The retrieve_and_generate API handles conversation context automatically when you provide a sessionId.

**Estimated Duration**: 1.5 days
**Estimated Token Count**: ~30,000 tokens

---

## Goals

- [ ] GraphQL schema updated for chat (sessionId parameter, ChatResponse type, Source type)
- [ ] QueryKB Lambda reads chat_model_id from ConfigurationManager
- [ ] SessionId parameter supported (optional, for conversation history)
- [ ] Enhanced citation parsing (extract documentId, pageNumber from S3 URIs)
- [ ] Error handling for session expiration and config failures
- [ ] Tests written and passing (80%+ coverage)
- [ ] Local verification via SAM

---

## Prerequisites

- Phases 1-2 complete (configuration system working)
- ConfigurationManager available in `lib/ragstack_common/config.py`
- Understand Bedrock retrieve_and_generate API (review AWS docs if needed)
- SAM local testing working (`sam build` succeeds)

---

## Architectural Context

### How Session Management Works

**Bedrock-Managed Sessions**:
- First request (no sessionId): Bedrock creates new session, returns sessionId
- Follow-up requests (with sessionId): Bedrock loads conversation history automatically
- Session TTL: 1 hour of inactivity
- No manual prompt construction needed (Bedrock handles context)

**Why This Approach**:
- Simpler than base repo's document chat (no manual history JSON)
- Lower cost than prompt caching (only retrieval tokens)
- Automatic context management by AWS

**Reference**: Use subagent to understand base repo's different approach:
```
Use explore-base-architecture to show how the base repository's chat_with_document Lambda handles conversation history manually
```

Compare with RAGStack's approach to understand the trade-offs.

---

## Tasks

### Task 3.1: Update GraphQL Schema for Chat

**Goal**: Add sessionId parameter and enhanced response types

**Files to Modify**:
- `src/api/schema.graphql`

**Prerequisites**: None (first task)

**Instructions**:

1. **Locate existing schema**:
   - Find the `queryKnowledgeBase` query definition
   - Note current return type (likely `SearchResult` or similar)
   - Understand current field structure

2. **Reference base repo pattern** (optional but recommended):
   ```
   Use explore-base-infrastructure to show GraphQL schema patterns for queries with optional parameters
   ```
   - Study how optional parameters are defined
   - Note the AWSJSON type usage for complex data

3. **Update query signature**:
```graphql
type Query {
  queryKnowledgeBase(
    query: String!
    sessionId: String  # NEW - optional for conversation
  ): ChatResponse      # CHANGED from SearchResult
}
```

4. **Add new ChatResponse type**:
```graphql
type ChatResponse {
  answer: String!
  sessionId: String!
  sources: [Source!]!
  error: String        # Optional error message
}

type Source {
  documentId: String!
  pageNumber: Int      # May be null for non-paginated docs
  s3Uri: String!
  snippet: String      # First 200 chars of source text
}
```

5. **Maintain backward compatibility**:
   - Existing Search page may use old type
   - If so, keep old type definition or update Search to use ChatResponse
   - Test that existing queries still work

**Verification Checklist**:

- [ ] GraphQL syntax is valid (no parse errors)
- [ ] sessionId parameter is optional (no `!` required marker)
- [ ] ChatResponse includes all fields needed by frontend
- [ ] Source type matches frontend expectations
- [ ] No breaking changes to existing queries

**Testing**:

Schema validation happens at build time. Run:
```bash
sam build
# Check for GraphQL schema errors in output
```

**Commit Message**:

```
feat(api): add chat support to GraphQL schema

- Add optional sessionId parameter to queryKnowledgeBase
- Create ChatResponse type with sessionId and sources
- Add Source type for structured citation data
- Maintain backward compatibility with existing queries
```

**Estimated Tokens**: ~5,000

---

### Task 3.2: Enhance QueryKB Lambda with Session Support

**Goal**: Add sessionId handling and dynamic model selection

**Files to Modify**:
- `src/lambda/query_kb/index.py`

**Prerequisites**: Task 3.1 complete

**Instructions**:

#### Step 1: Reference Base Repo Patterns

Before implementing, study existing patterns:

```
Use explore-base-architecture to show how Lambda functions are structured with module-level initialization and error handling
```

Key patterns to adopt:
- Module-level client initialization (reused across invocations)
- Graceful error handling with user-friendly messages
- Logging for debugging

```
Use config-pattern-finder to show how ConfigurationManager is used in Lambda functions to read effective configuration
```

Key patterns:
- Module-level ConfigurationManager instance
- Fallback to defaults when config unavailable
- Error handling for DynamoDB issues

#### Step 2: Update Lambda Handler

**Module-level initialization** (top of file):

```python
import os
import json
import logging
from urllib.parse import unquote
import boto3
from ragstack_common.config import ConfigurationManager

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients at module level (reused across invocations)
bedrock_agent = boto3.client('bedrock-agent-runtime')
config_manager = ConfigurationManager()

def lambda_handler(event, context):
    """
    Query Knowledge Base with optional session for conversation continuity.

    Args:
        event['arguments']['query'] (str): User's question
        event['arguments']['sessionId'] (str, optional): Conversation session ID

    Returns:
        dict: {
            'answer': str,
            'sessionId': str,
            'sources': list[dict],
            'error': str (optional)
        }
    """
    try:
        # Extract inputs
        query = event['arguments']['query']
        session_id = event['arguments'].get('sessionId')

        kb_id = os.environ['KNOWLEDGE_BASE_ID']
        region = os.environ['AWS_REGION']

        # Load chat model from configuration (with fallback)
        try:
            effective_config = config_manager.get_effective_config()
            model_id = effective_config.get('chat_model_id', 'us.amazon.nova-pro-v1:0')
        except Exception as e:
            logger.warning(f"Failed to load config, using default model: {e}")
            model_id = 'us.amazon.nova-pro-v1:0'

        # Build model ARN
        model_arn = f'arn:aws:bedrock:{region}::foundation-model/{model_id}'

        logger.info(f"Query KB with model: {model_id}, session: {session_id or 'new'}")

        # Build request
        request = {
            'input': {'text': query},
            'retrieveAndGenerateConfiguration': {
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': kb_id,
                    'modelArn': model_arn
                },
                'type': 'KNOWLEDGE_BASE'
            }
        }

        # Add sessionId if provided (for conversation continuity)
        if session_id:
            request['sessionId'] = session_id

        # Call Bedrock
        response = bedrock_agent.retrieve_and_generate(**request)

        # Extract data
        answer = response['output']['text']
        new_session_id = response['sessionId']
        citations = response.get('citations', [])

        logger.info(f"KB query successful. SessionId: {new_session_id}, Citations: {len(citations)}")

        # Parse sources
        sources = extract_sources(citations)

        return {
            'answer': answer,
            'sessionId': new_session_id,
            'sources': sources
        }

    except bedrock_agent.exceptions.ValidationException as e:
        # Handle session expiration specifically
        error_msg = str(e)
        if 'session' in error_msg.lower():
            logger.warning(f"Session expired: {session_id}")
            return {
                'error': 'Session expired. Please start a new conversation.',
                'answer': '',
                'sessionId': None,
                'sources': []
            }
        # Other validation errors
        logger.error(f"Validation error: {e}")
        return {
            'error': f"Invalid request: {error_msg}",
            'answer': '',
            'sessionId': None,
            'sources': []
        }

    except Exception as e:
        # Generic error handling
        logger.error(f"Error querying KB: {e}", exc_info=True)
        return {
            'error': 'Failed to query knowledge base. Please try again.',
            'answer': '',
            'sessionId': None,
            'sources': []
        }
```

#### Step 3: Implement Source Extraction

**Add extract_sources function**:

```python
def extract_sources(citations):
    """
    Parse Bedrock citations into structured sources.

    Args:
        citations (list): Bedrock citation objects from retrieve_and_generate

    Returns:
        list[dict]: Parsed sources with documentId, pageNumber, s3Uri, snippet

    Example citation structure:
        [{
            'retrievedReferences': [{
                'content': {'text': 'chunk text...'},
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/doc-id/pages/page-1.json'
                    }
                },
                'metadata': {...}
            }]
        }]
    """
    sources = []
    seen = set()  # Deduplicate sources

    for citation in citations:
        for ref in citation.get('retrievedReferences', []):
            # Extract S3 URI
            uri = ref.get('location', {}).get('s3Location', {}).get('uri', '')
            if not uri:
                continue

            # Parse S3 URI: s3://bucket/document-id/pages/page-1.json
            try:
                parts = uri.replace('s3://', '').split('/')
                if len(parts) < 2:
                    logger.warning(f"Invalid S3 URI format: {uri}")
                    continue

                # Decode document ID (may have URL encoding)
                document_id = unquote(parts[1])
                page_num = None

                # Extract page number if available
                if 'pages' in parts and len(parts) > 3:
                    page_file = parts[-1]  # e.g., "page-3.json"
                    try:
                        # Extract number from "page-3.json" -> 3
                        page_num = int(page_file.split('-')[1].split('.')[0])
                    except (IndexError, ValueError):
                        logger.debug(f"Could not extract page number from: {page_file}")

                # Deduplicate by document + page
                source_key = f"{document_id}:{page_num}"
                if source_key not in seen:
                    # Extract snippet (first 200 chars)
                    content_text = ref.get('content', {}).get('text', '')
                    snippet = content_text[:200] if content_text else ''

                    sources.append({
                        'documentId': document_id,
                        'pageNumber': page_num,
                        's3Uri': uri,
                        'snippet': snippet
                    })
                    seen.add(source_key)

            except Exception as e:
                logger.warning(f"Failed to parse source URI {uri}: {e}")
                continue

    logger.info(f"Extracted {len(sources)} unique sources from {len(citations)} citations")
    return sources
```

**Key Implementation Notes**:

1. **URL Decoding**: Document IDs may have spaces or special chars (use `unquote`)
2. **Page Number Parsing**: Handles both paginated and non-paginated docs
3. **Deduplication**: Same document+page may appear multiple times in citations
4. **Error Tolerance**: Malformed URIs don't crash the function
5. **Logging**: Helps debug source parsing issues

#### Step 4: Add Comprehensive Tests (TDD)

**Test File**: `src/lambda/query_kb/test_handler.py`

Write tests BEFORE implementing. Here's a comprehensive test suite:

```python
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from botocore.exceptions import ClientError
from index import lambda_handler, extract_sources

class TestQueryKBLambda:
    """Test QueryKB Lambda with session support and dynamic model selection"""

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_query_kb_with_session_id(self, mock_config, mock_bedrock):
        """Test that sessionId is passed to Bedrock for conversation continuity"""
        # Mock configuration
        mock_config.get_effective_config.return_value = {
            'chat_model_id': 'us.amazon.nova-pro-v1:0'
        }

        # Mock Bedrock response
        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Test answer'},
            'sessionId': 'session-123',
            'citations': []
        }

        # Event with sessionId
        event = {
            'arguments': {
                'query': 'Test query',
                'sessionId': 'session-123'
            }
        }

        result = lambda_handler(event, None)

        # Assertions
        assert result['answer'] == 'Test answer'
        assert result['sessionId'] == 'session-123'
        assert result['sources'] == []
        assert 'error' not in result or result['error'] is None

        # Verify sessionId was passed to Bedrock
        call_args = mock_bedrock.retrieve_and_generate.call_args
        assert call_args[1]['sessionId'] == 'session-123'

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_query_kb_without_session_id(self, mock_config, mock_bedrock):
        """Test new conversation (no sessionId) - Bedrock creates new session"""
        mock_config.get_effective_config.return_value = {
            'chat_model_id': 'us.amazon.nova-pro-v1:0'
        }

        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Test answer'},
            'sessionId': 'new-session-456',  # Bedrock returns new sessionId
            'citations': []
        }

        event = {
            'arguments': {
                'query': 'Test query'
                # No sessionId - new conversation
            }
        }

        result = lambda_handler(event, None)

        assert result['sessionId'] == 'new-session-456'

        # Verify sessionId NOT in request (new conversation)
        call_args = mock_bedrock.retrieve_and_generate.call_args
        assert 'sessionId' not in call_args[1]

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_reads_chat_model_from_config(self, mock_config, mock_bedrock):
        """Test that chat_model_id is read from configuration table"""
        # User selected Claude Sonnet in Settings
        mock_config.get_effective_config.return_value = {
            'chat_model_id': 'anthropic.claude-3-5-sonnet-20241022-v2:0'
        }

        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Answer'},
            'sessionId': 'session-789',
            'citations': []
        }

        event = {'arguments': {'query': 'Test'}}

        lambda_handler(event, None)

        # Verify correct model ARN built and used
        call_args = mock_bedrock.retrieve_and_generate.call_args
        config = call_args[1]['retrieveAndGenerateConfiguration']
        model_arn = config['knowledgeBaseConfiguration']['modelArn']

        assert 'anthropic.claude-3-5-sonnet-20241022-v2:0' in model_arn

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_config_load_failure_uses_fallback(self, mock_config, mock_bedrock):
        """Test graceful fallback when config table unavailable"""
        # Config manager throws error
        mock_config.get_effective_config.side_effect = Exception("DynamoDB unavailable")

        mock_bedrock.retrieve_and_generate.return_value = {
            'output': {'text': 'Answer'},
            'sessionId': 'session-999',
            'citations': []
        }

        event = {'arguments': {'query': 'Test'}}

        result = lambda_handler(event, None)

        # Should succeed with fallback model
        assert result['answer'] == 'Answer'

        # Verify fallback model used (us.amazon.nova-pro-v1:0)
        call_args = mock_bedrock.retrieve_and_generate.call_args
        model_arn = call_args[1]['retrieveAndGenerateConfiguration']['knowledgeBaseConfiguration']['modelArn']
        assert 'us.amazon.nova-pro-v1:0' in model_arn

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_session_expiration_error(self, mock_config, mock_bedrock):
        """Test graceful handling of expired session"""
        mock_config.get_effective_config.return_value = {'chat_model_id': 'us.amazon.nova-pro-v1:0'}

        # Bedrock returns validation error for expired session
        mock_bedrock.retrieve_and_generate.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid session ID'}},
            'retrieve_and_generate'
        )

        event = {'arguments': {'query': 'Test', 'sessionId': 'expired-session'}}

        result = lambda_handler(event, None)

        # Should return user-friendly error
        assert result['error'] is not None
        assert 'session' in result['error'].lower()
        assert 'expired' in result['error'].lower()
        assert result['sessionId'] is None
        assert result['answer'] == ''

    @patch('index.bedrock_agent')
    @patch('index.config_manager')
    def test_bedrock_api_error(self, mock_config, mock_bedrock):
        """Test handling of generic Bedrock errors"""
        mock_config.get_effective_config.return_value = {'chat_model_id': 'us.amazon.nova-pro-v1:0'}

        # Generic Bedrock error
        mock_bedrock.retrieve_and_generate.side_effect = Exception("Service unavailable")

        event = {'arguments': {'query': 'Test'}}

        result = lambda_handler(event, None)

        # Should return error but not crash
        assert result['error'] is not None
        assert result['answer'] == ''
        assert result['sessionId'] is None

    def test_extract_sources_parses_s3_uris(self):
        """Test source extraction from Bedrock citations"""
        citations = [{
            'retrievedReferences': [{
                'content': {'text': 'Sample text from document about invoices'},
                'location': {
                    's3Location': {
                        'uri': 's3://mybucket/my-document.pdf/pages/page-3.json'
                    }
                }
            }]
        }]

        sources = extract_sources(citations)

        assert len(sources) == 1
        assert sources[0]['documentId'] == 'my-document.pdf'
        assert sources[0]['pageNumber'] == 3
        assert sources[0]['s3Uri'] == 's3://mybucket/my-document.pdf/pages/page-3.json'
        assert 'Sample text' in sources[0]['snippet']
        assert len(sources[0]['snippet']) <= 200

    def test_extract_sources_handles_url_encoding(self):
        """Test that URL-encoded document names are decoded"""
        citations = [{
            'retrievedReferences': [{
                'content': {'text': 'Text'},
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/My%20Document%20With%20Spaces.pdf/pages/page-1.json'
                    }
                }
            }]
        }]

        sources = extract_sources(citations)

        assert sources[0]['documentId'] == 'My Document With Spaces.pdf'

    def test_extract_sources_deduplicates(self):
        """Test that duplicate sources (same doc + page) are filtered"""
        citations = [{
            'retrievedReferences': [
                {
                    'content': {'text': 'Text 1'},
                    'location': {'s3Location': {'uri': 's3://bucket/doc.pdf/pages/page-1.json'}}
                },
                {
                    'content': {'text': 'Text 2'},
                    'location': {'s3Location': {'uri': 's3://bucket/doc.pdf/pages/page-1.json'}}
                },
                {
                    'content': {'text': 'Text 3'},
                    'location': {'s3Location': {'uri': 's3://bucket/doc.pdf/pages/page-2.json'}}
                }
            ]
        }]

        sources = extract_sources(citations)

        # Should have 2 unique sources (page 1 deduplicated)
        assert len(sources) == 2

    def test_extract_sources_handles_missing_page_number(self):
        """Test sources without page numbers (non-paginated docs)"""
        citations = [{
            'retrievedReferences': [{
                'content': {'text': 'Text'},
                'location': {
                    's3Location': {
                        'uri': 's3://bucket/document.txt/vectors/chunk-1.json'
                    }
                }
            }]
        }]

        sources = extract_sources(citations)

        assert len(sources) == 1
        assert sources[0]['documentId'] == 'document.txt'
        assert sources[0]['pageNumber'] is None

    def test_extract_sources_handles_empty_citations(self):
        """Test that empty citations return empty sources"""
        assert extract_sources([]) == []
        assert extract_sources([{'retrievedReferences': []}]) == []

    def test_extract_sources_truncates_snippet(self):
        """Test that snippets are truncated to 200 chars"""
        long_text = 'A' * 500
        citations = [{
            'retrievedReferences': [{
                'content': {'text': long_text},
                'location': {'s3Location': {'uri': 's3://bucket/doc.pdf/pages/page-1.json'}}
            }]
        }]

        sources = extract_sources(citations)

        assert len(sources[0]['snippet']) == 200
```

**Run Tests**:

```bash
# Run QueryKB tests
pytest src/lambda/query_kb/test_handler.py -v

# With coverage
pytest src/lambda/query_kb/test_handler.py --cov=src/lambda/query_kb --cov-report=term

# Target: 80%+ coverage
```

**Verification Checklist**:

- [ ] All tests passing
- [ ] Tests cover happy path (with/without sessionId)
- [ ] Tests cover error cases (session expiration, config failure, Bedrock errors)
- [ ] Tests cover source extraction edge cases
- [ ] Coverage >= 80%

**Commit Message**:

```
feat(query-kb): add session support and dynamic model selection

- Add optional sessionId parameter for conversation continuity
- Read chat_model_id from ConfigurationManager (dynamic model selection)
- Implement extract_sources() to parse citations into structured data
- Handle session expiration gracefully with user-friendly errors
- Fallback to default model when config unavailable
- Add comprehensive test suite with 80%+ coverage
- Support URL-encoded document names and non-paginated docs
```

**Estimated Tokens**: ~15,000

---

### Task 3.3: Update AppSync Resolver Routing

**Goal**: Ensure AppSync resolver properly routes queryKnowledgeBase to QueryKB Lambda

**Files to Modify**:
- `src/lambda/appsync_resolvers/index.py`

**Prerequisites**: Task 3.2 complete

**Instructions**:

1. **Locate resolver routing logic**:
   - Find where `queryKnowledgeBase` field is handled
   - Likely in a switch/if statement based on `event['info']['fieldName']`

2. **Reference pattern** (if needed):
   ```
   Use explore-base-architecture to show how AppSync resolvers route different queries to different handlers
   ```

3. **Verify sessionId passthrough**:
   - Ensure `event['arguments']` is passed through to QueryKB Lambda
   - No filtering that would remove sessionId parameter
   - Likely already correct if routing is generic

**Expected pattern**:

```python
def lambda_handler(event, context):
    field_name = event['info']['fieldName']

    if field_name == 'queryKnowledgeBase':
        # Route to QueryKB Lambda
        # event['arguments'] already contains query and sessionId
        return query_kb_handler(event, context)
    # ... other routes
```

**Verification**:

Most likely no changes needed - AppSync resolvers typically pass all arguments through. Verify by checking:

- [ ] `event['arguments']` is not filtered
- [ ] No hardcoded argument list that excludes sessionId
- [ ] Routing is generic (passes full event)

**Testing**:

If changes made, write integration test:

```python
def test_appsync_routes_session_id_to_query_kb():
    """Test that sessionId is passed through AppSync resolver"""
    event = {
        'info': {'fieldName': 'queryKnowledgeBase'},
        'arguments': {
            'query': 'Test',
            'sessionId': 'session-123'
        }
    }

    # Mock QueryKB handler
    with patch('index.query_kb_handler') as mock_handler:
        mock_handler.return_value = {'answer': 'Test', 'sessionId': 'session-123', 'sources': []}

        from src.lambda.appsync_resolvers.index import lambda_handler
        result = lambda_handler(event, None)

        # Verify sessionId was passed
        call_args = mock_handler.call_args
        assert call_args[0][0]['arguments']['sessionId'] == 'session-123'
```

**Commit Message** (if changes needed):

```
fix(appsync): ensure sessionId parameter passed to QueryKB

- Verify argument passthrough for queryKnowledgeBase
- Add test for sessionId routing
```

**Estimated Tokens**: ~3,000

---

### Task 3.4: Local Verification with SAM

**Goal**: Test enhanced QueryKB Lambda locally with SAM Local

**Files to Create**:
- `tests/events/query_kb_new_session.json`
- `tests/events/query_kb_with_session.json`

**Prerequisites**: Tasks 3.1-3.3 complete, tests passing

**Instructions**:

#### Step 1: Create Test Events

**New conversation** (`tests/events/query_kb_new_session.json`):

```json
{
  "arguments": {
    "query": "What documents do we have about invoices?"
  }
}
```

**Follow-up with session** (`tests/events/query_kb_with_session.json`):

```json
{
  "arguments": {
    "query": "Show me the one from January",
    "sessionId": "test-session-123"
  }
}
```

**Session expiration test** (`tests/events/query_kb_expired_session.json`):

```json
{
  "arguments": {
    "query": "Test query",
    "sessionId": "expired-session-abc"
  }
}
```

#### Step 2: Build Lambda

```bash
# Build all Lambda functions
sam build

# Verify QueryKB built successfully
ls .aws-sam/build/QueryKBFunction/
```

#### Step 3: Test Locally

**Test new conversation**:

```bash
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json

# Expected output (partial):
# {
#   "answer": "Based on the knowledge base, ...",
#   "sessionId": "some-uuid-generated-by-bedrock",
#   "sources": [
#     {
#       "documentId": "invoice-2024.pdf",
#       "pageNumber": 1,
#       "s3Uri": "s3://...",
#       "snippet": "..."
#     }
#   ]
# }
```

**Test with session** (simulates follow-up):

```bash
sam local invoke QueryKBFunction -e tests/events/query_kb_with_session.json

# Note: Local testing may not have valid Bedrock session
# May return session expiration error (expected)
# Real session testing requires deployment
```

**Prettify output**:

```bash
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json | jq .

# Or save to file
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json > /tmp/response.json
cat /tmp/response.json | jq .
```

#### Step 4: Verify Response Structure

Check response includes:

- [ ] `answer` field (non-empty string)
- [ ] `sessionId` field (non-null)
- [ ] `sources` array (may be empty if no KB set up)
- [ ] No `error` field (or null)
- [ ] Sources have correct structure if present

**If errors occur**:

1. **"Knowledge Base not found"**: Expected if KB not configured locally
2. **"Config table not found"**: Expected if DynamoDB table doesn't exist locally
3. **Session errors**: Expected - real sessions require deployed Bedrock

**Success criteria for local testing**:

- Lambda invokes without crashes
- Response structure matches schema
- Logs show correct model ARN being built
- Error handling works (try invalid input)

#### Step 5: Test Configuration Loading

Verify dynamic model selection works:

```bash
# Check logs for model being used
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json 2>&1 | grep -i "model"

# Should see log like:
# INFO Query KB with model: us.amazon.nova-pro-v1:0, session: new
```

**Verification Checklist**:

- [ ] `sam build` succeeds without errors
- [ ] Lambda invokes locally without crashing
- [ ] Response structure matches ChatResponse schema
- [ ] Logs show correct model ARN
- [ ] Error handling works for missing resources
- [ ] Test events created and documented

**Commit Message**:

```
test(query-kb): add local verification events for chat

- Create test events for new conversation and session continuity
- Add session expiration test event
- Document expected responses and local testing limitations
- Verify response structure matches GraphQL schema
```

**Estimated Tokens**: ~4,000

---

### Task 3.5: Update IAM Permissions and Environment Variables

**Goal**: Grant QueryKB Lambda permissions to read configuration table

**Files to Modify**:
- `template.yaml`

**Prerequisites**: All previous tasks complete

**Instructions**:

1. **Locate QueryKBFunction in template.yaml**:
   - Find the AWS::Serverless::Function resource
   - Review existing Policies section

2. **Reference SAM policy patterns** (optional):
   ```
   Use explore-base-infrastructure to show DynamoDB read policy patterns in SAM template
   ```

3. **Add DynamoDB read permission**:

```yaml
QueryKBFunction:
  Type: AWS::Serverless::Function
  Properties:
    CodeUri: src/lambda/query_kb/
    Handler: index.lambda_handler
    Runtime: python3.13
    MemorySize: 512
    Timeout: 60
    Policies:
      # NEW: Permission to read configuration
      - DynamoDBReadPolicy:
          TableName: !Ref ConfigurationTable

      # EXISTING: Bedrock permissions
      - Statement:
          - Effect: Allow
            Action:
              - bedrock:InvokeModel
              - bedrock-agent-runtime:Retrieve
              - bedrock-agent-runtime:RetrieveAndGenerate
            Resource: '*'

      # EXISTING: Knowledge Base permissions (if separate)
      - Statement:
          - Effect: Allow
            Action:
              - bedrock:RetrieveAndGenerate
            Resource: !Sub 'arn:aws:bedrock:${AWS::Region}:${AWS::AccountId}:knowledge-base/${KnowledgeBaseId}'

    Environment:
      Variables:
        KNOWLEDGE_BASE_ID: !Ref KnowledgeBaseId
        AWS_REGION: !Ref AWS::Region
        CONFIGURATION_TABLE_NAME: !Ref ConfigurationTable  # NEW
        # Add any other env vars
```

4. **Verify environment variable reference**:
   - ConfigurationManager expects `CONFIGURATION_TABLE_NAME` env var
   - Ensure it's set correctly
   - If ConfigurationManager uses different name, update accordingly

**Reference**: Check ConfigurationManager implementation:

```python
# In lib/ragstack_common/config.py
table_name = os.environ.get('CONFIGURATION_TABLE_NAME', 'Configuration')
```

Ensure env var name matches what ConfigurationManager expects.

**Verification Checklist**:

- [ ] DynamoDBReadPolicy added for ConfigurationTable
- [ ] CONFIGURATION_TABLE_NAME environment variable set
- [ ] Bedrock permissions still present
- [ ] No syntax errors in YAML
- [ ] SAM validates template

**Testing**:

```bash
# Validate SAM template
sam validate

# Build with new permissions
sam build

# Check that env vars are set
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json --debug 2>&1 | grep CONFIGURATION_TABLE_NAME
```

**Commit Message**:

```
fix(iam): add ConfigurationTable read permission to QueryKB

- Grant DynamoDBReadPolicy for reading chat_model_id
- Add CONFIGURATION_TABLE_NAME environment variable
- Enable dynamic model selection from Settings
- Verify SAM template validates successfully
```

**Estimated Tokens**: ~3,000

---

## Troubleshooting Guide

### Common Issues and Solutions

**Issue 1: ConfigurationManager import fails**

```
ModuleNotFoundError: No module named 'ragstack_common'
```

**Cause**: Shared library not built into Lambda package

**Solution**:
- Check `template.yaml` has build configuration for shared lib
- Run `sam build` to copy shared lib to Lambda
- Verify `.aws-sam/build/QueryKBFunction/ragstack_common/` exists

---

**Issue 2: Session expiration not detected**

```
Bedrock returns error but Lambda doesn't return user-friendly message
```

**Cause**: Error detection logic not matching actual exception

**Solution**:
- Check exact exception type and message from Bedrock
- Update error detection in try/except block
- Test with actual expired sessionId

---

**Issue 3: Sources not parsing correctly**

```
sources array is empty even though citations exist
```

**Cause**: S3 URI format doesn't match expected pattern

**Solution**:
- Log actual S3 URIs from Bedrock response
- Check vector bucket structure (may differ from expected)
- Update regex/split logic in extract_sources
- Handle different URI formats gracefully

---

**Issue 4: Wrong model being used**

```
Expected Claude but Nova is being used
```

**Cause**: Configuration not loaded or fallback triggered

**Solution**:
- Check ConfigurationManager logs
- Verify DynamoDB table has correct data
- Check IAM permissions for table read
- Ensure CONFIGURATION_TABLE_NAME env var set
- Verify model_id in effective_config

---

**Issue 5: SAM local invoke fails**

```
Error: Lambda container exited before handler ran
```

**Cause**: Syntax error or missing dependency

**Solution**:
- Check Lambda logs: `sam logs -n QueryKBFunction --tail`
- Verify Python syntax with linter
- Ensure all imports available in Lambda environment
- Check function timeout not too short

---

## Phase 3 Summary

### What You Built

- ✅ **GraphQL Schema**: Added sessionId parameter and ChatResponse type
- ✅ **Session Management**: Bedrock handles conversation context automatically
- ✅ **Dynamic Model Selection**: Reads chat_model_id from configuration table
- ✅ **Source Parsing**: Extracts documentId and pageNumber from S3 URIs
- ✅ **Error Handling**: Session expiration, config failures, Bedrock errors
- ✅ **Testing**: 80%+ coverage with comprehensive test suite
- ✅ **IAM Permissions**: QueryKB can read configuration table
- ✅ **Local Verification**: SAM local testing confirms functionality

### Test Coverage

**Unit Tests**:
- Session handling (with/without sessionId)
- Dynamic model selection from config
- Config fallback when table unavailable
- Source extraction (various URI formats)
- URL decoding and deduplication
- Snippet truncation

**Integration Tests**:
- AppSync resolver routing (if changed)
- End-to-end Lambda invocation

**Error Handling Tests**:
- Session expiration (ValidationException)
- Generic Bedrock errors
- Config loading failures
- Malformed source URIs

### Commits Made

Expected ~3-4 commits:
1. GraphQL schema updates for chat support
2. QueryKB Lambda enhancement with tests
3. AppSync resolver fix (if needed)
4. IAM permissions and verification events

### Verification Steps

**All tests passing**:
```bash
pytest src/lambda/query_kb/test_handler.py -v --cov
# Target: 80%+ coverage achieved
```

**SAM build succeeds**:
```bash
sam build
sam validate
```

**Local invocation works**:
```bash
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json | jq .
# Response structure matches ChatResponse schema
```

**Logs show correct behavior**:
```bash
# Check model selection
sam local invoke QueryKBFunction -e tests/events/query_kb_new_session.json 2>&1 | grep "Query KB with model"

# Should show: INFO Query KB with model: us.amazon.nova-pro-v1:0
```

### Key Learnings

**Session Management**:
- Bedrock manages history automatically (simpler than manual history)
- Sessions expire after 1 hour inactivity
- Frontend stores sessionId, backend passes through

**Model Selection**:
- Runtime configuration via DynamoDB (no redeployment needed)
- Graceful fallback ensures uptime even if config unavailable
- Users can switch between Nova Lite (cheap) and Claude Sonnet (quality)

**Source Parsing**:
- S3 URIs encode document structure (bucket/doc/pages/page-N.json)
- URL decoding required for docs with spaces
- Deduplication needed (same chunk may appear multiple times)

---

## Next Steps

**Backend complete!** The QueryKB Lambda now supports conversational chat.

→ **[Continue to Phase 4: Chat Frontend](Phase-4.md)**

Phase 4 will build the chat UI components that leverage this backend functionality.

---

**Phase 3 Estimated Token Total**: ~30,000 tokens
