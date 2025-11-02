# Phase 1: Settings Backend - Configuration Schema & GraphQL

## Overview

This phase adds three new configuration fields to the backend:
1. `ocr_backend` - Choose between Textract or Bedrock OCR
2. `bedrock_ocr_model_id` - Select Claude model for Bedrock OCR (conditional field)
3. `chat_model_id` - Select model for Knowledge Base queries

**Approach**: Update GraphQL schema and resolver to return enhanced configuration. The existing DynamoDB Configuration table and ConfigurationManager already support arbitrary fields, so no database changes are needed.

**Estimated Duration**: 1 day
**Estimated Token Count**: ~25,000 tokens

---

## Goals

By the end of this phase:

- [ ] GraphQL schema updated with new configuration fields
- [ ] Configuration schema includes 3 new fields with proper types and metadata
- [ ] Default configuration values established for all fields
- [ ] Tests written and passing for configuration retrieval
- [ ] Changes committed with clear message

---

## Prerequisites

- Phase 0 read and understood
- Environment verified (sam build works)
- Familiar with GraphQL schema syntax
- Understand ConfigurationManager pattern (see Phase 0 ADRs)

---

## Tasks

### Task 1.1: Update GraphQL Schema

**Goal**: Enhance the GraphQL schema type to support new configuration fields

**Files to Modify**:
- `src/api/schema.graphql`

**Prerequisites**: None (first task)

**Instructions**:

The GraphQL schema defines the API contract. You'll update the configuration-related types to include metadata for the three new fields.

**Steps**:

1. **Locate configuration types** in `src/api/schema.graphql`
   - Find the `getConfiguration` query definition
   - Find the return type (likely named `Configuration` or similar)
   - Understand current structure

2. **Review base repository pattern** (optional, for context):
   - Use subagent: "Use config-pattern-finder to show the configuration schema structure in the base repository"
   - Understand how schema, default, and custom configurations are structured

3. **Update schema definition** to document new fields:
   - The schema returned by `getConfiguration` contains a `Schema` property (JSON)
   - This Schema defines field metadata (type, enum values, description, order, dependsOn)
   - No GraphQL type changes needed - Configuration already returns AWSJSON for Schema/Default/Custom
   - Document the new fields in code comments for clarity

4. **Verify schema syntax**:
   - Ensure GraphQL is valid
   - No breaking changes to existing queries/mutations

**Verification Checklist**:

- [ ] GraphQL schema file is syntactically valid
- [ ] Existing `getConfiguration` query unchanged
- [ ] Comments document the three new fields
- [ ] No breaking changes to existing types

**Testing**:

No tests needed for this task - schema validation happens at build time.

**Commit Message**:

```
docs(api): document new configuration fields in GraphQL schema

- Add documentation for ocr_backend field
- Add documentation for bedrock_ocr_model_id field
- Add documentation for chat_model_id field
- No breaking changes to API contract
```

**Estimated Tokens**: ~3,000

---

### Task 1.2: Define Configuration Schema with New Fields

**Goal**: Update the configuration schema to include three new fields with proper metadata

**Files to Modify**:
- `src/lambda/appsync_resolvers/index.py` (or wherever `getConfiguration` is implemented)

**Prerequisites**: Task 1.1 complete

**Instructions**:

The configuration system uses a schema-driven approach where field metadata is defined in the Schema object. The frontend uses this schema to render form fields dynamically.

**Steps**:

1. **Locate getConfiguration implementation**:
   - Find where `getConfiguration` query is handled
   - Likely in `src/lambda/appsync_resolvers/index.py`
   - Look for function that returns Schema, Default, and Custom configuration

2. **Review existing schema structure**:
   - Examine how `text_embed_model_id` and `image_embed_model_id` are defined
   - Note the pattern: `{ "type": "string", "enum": [...], "description": "...", "order": N }`
   - Understand the `dependsOn` pattern for conditional fields

3. **Reference base repository pattern** (recommended):
   - Use subagent: "Use config-pattern-finder to show how configuration schema fields are defined with enum and dependsOn"
   - Study the metadata structure
   - Note the order property for field sorting

4. **Add three new fields to Schema**:

   **Field 1 - ocr_backend**:
   ```python
   "ocr_backend": {
       "type": "string",
       "enum": ["textract", "bedrock"],
       "description": "OCR Backend",
       "order": 1
   }
   ```

   **Field 2 - bedrock_ocr_model_id** (conditional):
   ```python
   "bedrock_ocr_model_id": {
       "type": "string",
       "enum": [
           "anthropic.claude-3-5-haiku-20241022-v1:0",
           "anthropic.claude-3-5-sonnet-20241022-v2:0",
           "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
       ],
       "description": "Bedrock OCR Model",
       "order": 2,
       "dependsOn": {
           "field": "ocr_backend",
           "value": "bedrock"
       }
   }
   ```

   **Field 3 - chat_model_id**:
   ```python
   "chat_model_id": {
       "type": "string",
       "enum": [
           "us.amazon.nova-pro-v1:0",
           "us.amazon.nova-lite-v1:0",
           "anthropic.claude-3-5-sonnet-20241022-v2:0",
           "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
       ],
       "description": "Chat Model",
       "order": 3
   }
   ```

5. **Update existing field order** (if needed):
   - Adjust `order` property of existing embedding fields to 4 and 5
   - Ensures proper display order in UI

6. **Update Default configuration**:
   - Add default values for the three new fields:
   ```python
   "ocr_backend": "textract",
   "bedrock_ocr_model_id": "anthropic.claude-3-5-haiku-20241022-v1:0",
   "chat_model_id": "us.amazon.nova-pro-v1:0"
   ```

7. **Handle Custom configuration**:
   - No changes needed - Custom is user-provided overrides
   - Empty object by default

**Verification Checklist**:

- [ ] All three fields added to Schema with correct structure
- [ ] `dependsOn` correctly configured for `bedrock_ocr_model_id`
- [ ] `order` property set for proper field sorting
- [ ] Default values provided for all new fields
- [ ] Existing fields (embedding models) preserved
- [ ] Schema is valid JSON/Python dict

**Testing**:

Write tests BEFORE implementing:

**Test File**: `src/lambda/appsync_resolvers/test_configuration.py` (create if needed)

```python
import pytest
import json
from index import lambda_handler  # Adjust import based on structure

def test_get_configuration_includes_new_fields():
    """Test that getConfiguration returns schema with new OCR and chat fields"""
    event = {
        'info': {'fieldName': 'getConfiguration'},
        'arguments': {}
    }

    response = lambda_handler(event, None)
    config = json.loads(response) if isinstance(response, str) else response

    schema = json.loads(config['Schema'])

    # Assert new fields exist in schema
    assert 'ocr_backend' in schema['properties']
    assert 'bedrock_ocr_model_id' in schema['properties']
    assert 'chat_model_id' in schema['properties']

    # Assert ocr_backend structure
    ocr_field = schema['properties']['ocr_backend']
    assert ocr_field['type'] == 'string'
    assert set(ocr_field['enum']) == {'textract', 'bedrock'}
    assert ocr_field['order'] == 1

    # Assert bedrock_ocr_model_id has dependsOn
    bedrock_model_field = schema['properties']['bedrock_ocr_model_id']
    assert 'dependsOn' in bedrock_model_field
    assert bedrock_model_field['dependsOn']['field'] == 'ocr_backend'
    assert bedrock_model_field['dependsOn']['value'] == 'bedrock'

    # Assert chat_model_id structure
    chat_field = schema['properties']['chat_model_id']
    assert chat_field['type'] == 'string'
    assert len(chat_field['enum']) >= 4  # Should have multiple model options

def test_get_configuration_includes_default_values():
    """Test that default configuration includes new fields"""
    event = {
        'info': {'fieldName': 'getConfiguration'},
        'arguments': {}
    }

    response = lambda_handler(event, None)
    config = json.loads(response) if isinstance(response, str) else response

    defaults = json.loads(config['Default'])

    # Assert defaults exist
    assert defaults['ocr_backend'] == 'textract'
    assert defaults['bedrock_ocr_model_id'] == 'anthropic.claude-3-5-haiku-20241022-v1:0'
    assert defaults['chat_model_id'] == 'us.amazon.nova-pro-v1:0'

    # Assert existing defaults preserved
    assert 'text_embed_model_id' in defaults
    assert 'image_embed_model_id' in defaults

def test_field_ordering():
    """Test that fields have correct order property for UI sorting"""
    event = {
        'info': {'fieldName': 'getConfiguration'},
        'arguments': {}
    }

    response = lambda_handler(event, None)
    config = json.loads(response) if isinstance(response, str) else response
    schema = json.loads(config['Schema'])

    # Get all orders
    ocr_order = schema['properties']['ocr_backend']['order']
    bedrock_order = schema['properties']['bedrock_ocr_model_id']['order']
    chat_order = schema['properties']['chat_model_id']['order']

    # Assert logical ordering (OCR fields first, then chat, then embeddings)
    assert ocr_order == 1
    assert bedrock_order == 2
    assert chat_order == 3
```

**Test Execution**:

Run tests in TDD fashion:

1. Write tests first (above)
2. Run tests - they should FAIL (Red)
3. Implement the schema updates
4. Run tests again - they should PASS (Green)
5. Refactor if needed, keeping tests green

**Commands** (adjust based on your test setup):

```bash
# Run tests for this module
pytest src/lambda/appsync_resolvers/test_configuration.py -v

# Or run all Lambda tests
pytest src/lambda/ -v

# With coverage
pytest src/lambda/appsync_resolvers/ --cov=src/lambda/appsync_resolvers --cov-report=term
```

**Commit Message**:

```
feat(config): add OCR backend and chat model configuration fields

- Add ocr_backend field with textract/bedrock options
- Add bedrock_ocr_model_id with conditional dependsOn
- Add chat_model_id with Nova and Claude model options
- Include default values for all new fields
- Preserve existing embedding model configuration
- Add comprehensive tests for new schema fields
```

**Estimated Tokens**: ~12,000

---

### Task 1.3: Verify Local Configuration Retrieval

**Goal**: Test that configuration can be retrieved via SAM Local and verify schema structure

**Files to Use**:
- SAM CLI for local testing
- Existing GraphQL test events

**Prerequisites**: Task 1.2 complete and tests passing

**Instructions**:

Use SAM Local to invoke the AppSync resolver and verify the configuration response.

**Steps**:

1. **Build Lambda functions**:
   - Run sam build to compile latest changes
   - Ensure no build errors

2. **Create test event** (if not exists):
   - Create `tests/events/get_configuration.json`:
   ```json
   {
     "info": {
       "fieldName": "getConfiguration"
     },
     "arguments": {}
   }
   ```

3. **Invoke locally**:
   - Use SAM CLI to test the resolver
   - Examine the response structure

4. **Verify response**:
   - Schema includes all 7 fields (3 new + 4 existing)
   - Default values are correct
   - Custom is empty object (or user overrides if any)
   - dependsOn structure is correct for bedrock_ocr_model_id

5. **Check field ordering**:
   - Verify order property values are sequential
   - OCR fields come first (order 1-2)
   - Chat field next (order 3)
   - Embedding fields last (order 4-5)

**Verification Checklist**:

- [ ] `sam build` completes without errors
- [ ] Local invocation returns valid JSON
- [ ] Schema contains all 7 configuration fields
- [ ] Default values match specification
- [ ] dependsOn structure correct for conditional field
- [ ] Field order property enables correct UI sorting

**Testing**:

Manual testing via SAM Local:

```bash
# Build
sam build

# Invoke resolver locally
sam local invoke AppSyncResolverFunction -e tests/events/get_configuration.json

# Expected output (partial):
# {
#   "Schema": "{\"properties\": {\"ocr_backend\": {...}, ...}}",
#   "Default": "{\"ocr_backend\": \"textract\", ...}",
#   "Custom": "{}"
# }

# Prettify output for review
sam local invoke AppSyncResolverFunction -e tests/events/get_configuration.json | jq .
```

**Commit Message**:

```
test(config): add local verification test for configuration schema

- Create test event for getConfiguration query
- Verify schema structure with SAM local invoke
- Confirm all fields present and correctly ordered
```

**Estimated Tokens**: ~5,000

---

### Task 1.4: Integration Test for ConfigurationManager

**Goal**: Ensure ConfigurationManager can read and merge new configuration fields correctly

**Files to Modify**:
- `lib/ragstack_common/test_config.py` (create or update)

**Prerequisites**: Tasks 1.1-1.3 complete

**Instructions**:

The ConfigurationManager in `lib/ragstack_common/config.py` handles reading from DynamoDB and merging Custom over Default values. Write tests to ensure it handles the new fields correctly.

**Steps**:

1. **Review ConfigurationManager** (if unfamiliar):
   - Use subagent: "Use config-pattern-finder to show how ConfigurationManager.get_effective_config() works"
   - Understand the merge logic (Custom overrides Default)
   - Note any caching behavior

2. **Locate or create test file**:
   - Check if `lib/ragstack_common/test_config.py` exists
   - Create if needed

3. **Write integration tests**:

**Test File**: `lib/ragstack_common/test_config.py`

```python
import pytest
import json
from unittest.mock import Mock, patch
from ragstack_common.config import ConfigurationManager

class TestConfigurationManager:
    """Test ConfigurationManager with new OCR and chat fields"""

    @patch('ragstack_common.config.boto3')
    def test_get_effective_config_merges_custom_over_default(self, mock_boto3):
        """Test that Custom configuration overrides Default for new fields"""
        # Mock DynamoDB response
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        mock_table.get_item.return_value = {
            'Item': {
                'Configuration': 'Default',
                'Schema': json.dumps({
                    'properties': {
                        'ocr_backend': {'type': 'string', 'enum': ['textract', 'bedrock']},
                        'chat_model_id': {'type': 'string', 'enum': ['us.amazon.nova-pro-v1:0']}
                    }
                }),
                'Default': json.dumps({
                    'ocr_backend': 'textract',
                    'bedrock_ocr_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0',
                    'chat_model_id': 'us.amazon.nova-pro-v1:0'
                }),
                'Custom': json.dumps({
                    'ocr_backend': 'bedrock',  # User override
                    'chat_model_id': 'anthropic.claude-3-5-sonnet-20241022-v2:0'  # User override
                })
            }
        }

        # Get effective config
        config_mgr = ConfigurationManager()
        effective = config_mgr.get_effective_config()

        # Assert Custom values override Default
        assert effective['ocr_backend'] == 'bedrock'  # Custom override
        assert effective['chat_model_id'] == 'anthropic.claude-3-5-sonnet-20241022-v2:0'  # Custom override
        assert effective['bedrock_ocr_model_id'] == 'anthropic.claude-3-5-haiku-20241022-v1:0'  # Default (no override)

    @patch('ragstack_common.config.boto3')
    def test_get_effective_config_with_no_custom(self, mock_boto3):
        """Test that Default values are used when no Custom overrides exist"""
        mock_table = Mock()
        mock_boto3.resource.return_value.Table.return_value = mock_table

        mock_table.get_item.return_value = {
            'Item': {
                'Configuration': 'Default',
                'Schema': json.dumps({'properties': {}}),
                'Default': json.dumps({
                    'ocr_backend': 'textract',
                    'bedrock_ocr_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0',
                    'chat_model_id': 'us.amazon.nova-pro-v1:0'
                }),
                'Custom': '{}'  # No overrides
            }
        }

        config_mgr = ConfigurationManager()
        effective = config_mgr.get_effective_config()

        # Assert all values are from Default
        assert effective['ocr_backend'] == 'textract'
        assert effective['bedrock_ocr_model_id'] == 'anthropic.claude-3-5-haiku-20241022-v1:0'
        assert effective['chat_model_id'] == 'us.amazon.nova-pro-v1:0'

    @patch('ragstack_common.config.boto3')
    def test_fallback_to_hardcoded_defaults_on_error(self, mock_boto3):
        """Test graceful degradation when DynamoDB is unavailable"""
        mock_boto3.resource.return_value.Table.return_value.get_item.side_effect = Exception("DynamoDB unavailable")

        config_mgr = ConfigurationManager()

        # Should not raise, should return hardcoded defaults
        try:
            effective = config_mgr.get_effective_config()
            # Verify critical fields have fallback values
            assert 'ocr_backend' in effective or effective.get('ocr_backend') is not None
        except Exception:
            pytest.fail("ConfigurationManager should handle DynamoDB errors gracefully")
```

4. **Update ConfigurationManager fallback** (if needed):
   - Ensure ConfigurationManager has hardcoded fallback defaults for the new fields
   - This ensures graceful degradation if DynamoDB is unavailable
   - Add to fallback dict:
   ```python
   fallback_defaults = {
       'ocr_backend': 'textract',
       'bedrock_ocr_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0',
       'chat_model_id': 'us.amazon.nova-pro-v1:0',
       'text_embed_model_id': 'amazon.titan-embed-text-v2:0',
       'image_embed_model_id': 'amazon.titan-embed-image-v1'
   }
   ```

**Verification Checklist**:

- [ ] Tests written for merge logic (Custom over Default)
- [ ] Tests written for Default-only scenario
- [ ] Tests written for error handling/fallback
- [ ] ConfigurationManager has hardcoded fallbacks for new fields
- [ ] All tests passing

**Testing**:

```bash
# Run ConfigurationManager tests
pytest lib/ragstack_common/test_config.py -v

# With coverage
pytest lib/ragstack_common/test_config.py --cov=lib/ragstack_common/config --cov-report=term
```

**Commit Message**:

```
test(config): add tests for ConfigurationManager with new fields

- Test Custom configuration merges over Default
- Test Default values used when no Custom overrides
- Test graceful fallback when DynamoDB unavailable
- Add hardcoded defaults for OCR and chat fields
- Ensure 80%+ coverage for ConfigurationManager
```

**Estimated Tokens**: ~8,000

---

## Phase 1 Summary

### What You Built

- ✅ Updated GraphQL schema documentation for new configuration fields
- ✅ Added 3 new fields to configuration Schema (ocr_backend, bedrock_ocr_model_id, chat_model_id)
- ✅ Set Default values for all new fields
- ✅ Implemented conditional field logic (dependsOn for Bedrock model)
- ✅ Verified configuration retrieval via SAM Local
- ✅ Tested ConfigurationManager merge logic
- ✅ Ensured graceful fallback for error scenarios

### Test Coverage

- Configuration schema validation (structure, types, enums)
- Default values verification
- Field ordering for UI rendering
- ConfigurationManager merge logic (Custom → Default)
- Error handling and fallback defaults

### Commits Made

Expected ~2-3 commits:
1. Documentation update for GraphQL schema
2. Configuration schema with new fields + tests
3. ConfigurationManager integration tests

### Verification

Run these commands to verify Phase 1 completion:

```bash
# All tests passing
pytest src/lambda/appsync_resolvers/test_configuration.py -v
pytest lib/ragstack_common/test_config.py -v

# Build successful
sam build

# Local invocation works
sam local invoke AppSyncResolverFunction -e tests/events/get_configuration.json | jq .

# Expected output shows 7 fields in Schema
```

### Next Steps

**Backend complete!** The configuration system now supports the three new fields.

→ **[Continue to Phase 2: Settings Frontend](Phase-2.md)**

Phase 2 will update the Settings UI to render the new fields dynamically.

---

**Phase 1 Estimated Token Total**: ~25,000 tokens
