# Phase 1: SAM Foundations

**Goal:** Extend ConfigurationTable schema with chat settings and add web component source packaging to publish.py.

**Dependencies:** Phase 0 (read ADRs)

**Deliverables:**
- Extended `seed_configuration_table()` with chat fields
- New `package_amplify_chat_source()` function in publish.py
- Unit tests for schema validation and packaging logic

**Estimated Scope:** ~15,000 tokens

---

## Context

This phase prepares SAM infrastructure for Amplify chat integration:

1. **ConfigurationTable Schema** - Adds chat-specific fields that Phase 4 (Amplify runtime) will read and Phase 5 (SAM UI) will modify
2. **Source Packaging** - Adds function to package `src/amplify-chat/` for CodeBuild deployment (Phase 3 will use this)

These are **foundation tasks** - later phases depend on these contracts being correct.

---

## Task 1: Extend ConfigurationTable Schema

### Goal

Add chat configuration fields to the existing `seed_configuration_table()` function in `publish.py`.

### Files to Modify

- `publish.py` (function: `seed_configuration_table()`, lines 856-959)

### Background

Current schema has 3 OCR-related fields:
- `ocr_backend`
- `bedrock_ocr_model_id`
- `chat_model_id` (for Knowledge Base queries)

We're adding 7 new chat-specific fields following the same pattern.

### Instructions

1. **Locate the function:**
   - Open `publish.py`
   - Find `def seed_configuration_table(stack_name, region):` around line 856
   - Read the existing `schema_item` and `default_item` dictionaries

2. **Add chat fields to schema_item['Schema']['properties']:**

   After the existing `chat_model_id` property, add these fields (maintaining `order` sequence):

   ```python
   'chat_require_auth': {
       'type': 'boolean',
       'order': 4,
       'description': 'Require authentication for chat access',
       'default': False
   },
   'chat_primary_model': {
       'type': 'string',
       'order': 5,
       'description': 'Primary Bedrock model for chat (before quota limits)',
       'enum': [
           'us.anthropic.claude-sonnet-4-20250514-v1:0',
           'us.anthropic.claude-haiku-4-5-20251001-v1:0',
           'us.amazon.nova-pro-v1:0',
           'us.amazon.nova-lite-v1:0',
       ],
       'default': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
   },
   'chat_fallback_model': {
       'type': 'string',
       'order': 6,
       'description': 'Fallback model when quotas exceeded',
       'enum': [
           'us.anthropic.claude-haiku-4-5-20251001-v1:0',
           'us.amazon.nova-micro-v1:0',
           'us.amazon.nova-lite-v1:0',
       ],
       'default': 'us.amazon.nova-micro-v1:0'
   },
   'chat_global_quota_daily': {
       'type': 'number',
       'order': 7,
       'description': 'Max messages per day (all users combined) on primary model',
       'default': 10000
   },
   'chat_per_user_quota_daily': {
       'type': 'number',
       'order': 8,
       'description': 'Max messages per user per day on primary model',
       'default': 100
   },
   'chat_theme_preset': {
       'type': 'string',
       'order': 9,
       'description': 'UI theme preset',
       'enum': ['light', 'dark', 'brand'],
       'default': 'light'
   },
   'chat_theme_overrides': {
       'type': 'object',
       'order': 10,
       'description': 'Custom theme overrides (optional)',
       'properties': {
           'primaryColor': {'type': 'string'},
           'fontFamily': {'type': 'string'},
           'spacing': {
               'type': 'string',
               'enum': ['compact', 'comfortable', 'spacious']
           }
       }
   }
   ```

3. **Add chat fields to default_item:**

   After the existing fields in `default_item`, add:

   ```python
   'chat_require_auth': False,
   'chat_primary_model': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
   'chat_fallback_model': 'us.amazon.nova-micro-v1:0',
   'chat_global_quota_daily': 10000,
   'chat_per_user_quota_daily': 100,
   'chat_theme_preset': 'light',
   'chat_theme_overrides': {}
   ```

4. **Update required fields (optional enhancement):**

   In `schema_item['Schema']`, the `required` array currently has `['ocr_backend']`. Consider if `chat_primary_model` should be required when chat is deployed. For now, leave it as-is (not required).

5. **Verify syntax:**
   - Ensure proper comma placement between fields
   - Check dictionary nesting matches existing pattern
   - Run `python -m py_compile publish.py` to check syntax

### Verification Checklist

- [ ] Schema has 7 new chat fields (order 4-10)
- [ ] Each field has correct type, description, default
- [ ] Enum fields have valid model ARNs
- [ ] Default item has matching fields with default values
- [ ] No syntax errors (`python -m py_compile publish.py` passes)
- [ ] Existing OCR fields unchanged

### Testing

Create `tests/test_seed_configuration.py`:

```python
"""Tests for ConfigurationTable seeding with chat fields."""
import pytest
from unittest.mock import MagicMock, patch
from publish import seed_configuration_table


def test_chat_schema_has_required_fields():
    """Verify chat schema includes all required fields."""
    # Mock DynamoDB table
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            # Mock CloudFormation describe_stacks
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            # Mock DynamoDB table
            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call function
            seed_configuration_table('test-stack', 'us-east-1')

            # Get the schema item that was put
            calls = mock_table.put_item.call_args_list
            schema_call = calls[0]
            schema_item = schema_call[1]['Item']

            # Verify chat fields exist
            props = schema_item['Schema']['properties']
            assert 'chat_require_auth' in props
            assert 'chat_primary_model' in props
            assert 'chat_fallback_model' in props
            assert 'chat_global_quota_daily' in props
            assert 'chat_per_user_quota_daily' in props
            assert 'chat_theme_preset' in props
            assert 'chat_theme_overrides' in props


def test_chat_default_values():
    """Verify default configuration has correct chat values."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            seed_configuration_table('test-stack', 'us-east-1')

            # Get the default item
            calls = mock_table.put_item.call_args_list
            default_call = calls[1]
            default_item = default_call[1]['Item']

            # Verify defaults
            assert default_item['chat_require_auth'] is False
            assert default_item['chat_primary_model'] == 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
            assert default_item['chat_fallback_model'] == 'us.amazon.nova-micro-v1:0'
            assert default_item['chat_global_quota_daily'] == 10000
            assert default_item['chat_per_user_quota_daily'] == 100
            assert default_item['chat_theme_preset'] == 'light'
            assert default_item['chat_theme_overrides'] == {}


def test_chat_theme_preset_enum():
    """Verify theme preset has correct enum values."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            seed_configuration_table('test-stack', 'us-east-1')

            calls = mock_table.put_item.call_args_list
            schema_item = calls[0][1]['Item']

            theme_enum = schema_item['Schema']['properties']['chat_theme_preset']['enum']
            assert theme_enum == ['light', 'dark', 'brand']
```

Run tests:
```bash
pytest tests/test_seed_configuration.py -v
```

### Commit

```bash
git add publish.py tests/test_seed_configuration.py
git commit -m "feat(config): extend ConfigurationTable schema with chat fields

- Add 7 chat configuration fields to schema
- Set conservative defaults (auth off, 10k global quota, 100 per-user)
- Add theme preset and override support
- Include unit tests for schema structure and defaults"
```

---

## Task 2: Add Web Component Source Packaging Function

### Goal

Create `package_amplify_chat_source()` function that packages `src/amplify-chat/` into a zip file and uploads to S3, following the same pattern as `package_ui_source()`.

### Files to Modify

- `publish.py` (add new function after `package_ui_source()`)

### Background

The existing `package_ui_source()` function (lines 576-654) packages `src/ui/` into a zip, excludes `node_modules` and `build`, uploads to S3, and returns the S3 key.

We need an identical pattern for `src/amplify-chat/`, but the zip structure is different:
- `package_ui_source()` creates: `ui/package.json`, `ui/src/...`
- `package_amplify_chat_source()` creates: `web-component/package.json`, `web-component/src/...`

This naming matches Phase 3's CodeBuild expectation (see Phase-0 ADR-4).

### Instructions

1. **Locate insertion point:**
   - Find `package_ui_source()` function (around line 576)
   - After its closing, add new function

2. **Create the function:**

   ```python
   def package_amplify_chat_source(bucket_name, region):
       """
       Package web component source code as zip and upload to S3.

       Creates a zip file of src/amplify-chat/ (excluding node_modules and dist),
       uploads it to the provided S3 bucket, and returns the S3 key for CodeBuild.

       Args:
           bucket_name: S3 bucket name to upload to
           region: AWS region for bucket operations

       Returns:
           str: S3 key of uploaded web component source zip

       Raises:
           FileNotFoundError: If src/amplify-chat/ doesn't exist
           IOError: If packaging or upload fails
       """
       import zipfile
       import tempfile
       import time
       from pathlib import Path

       log_info("Packaging web component source...")

       chat_dir = Path('src/amplify-chat')
       if not chat_dir.exists():
           raise FileNotFoundError(f"Web component directory not found: {chat_dir}")

       # Create temporary zip file
       with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
           zip_path = tmp_file.name

       try:
           # Create zip file, excluding node_modules and dist
           log_info("Creating web component source zip file...")
           with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
               for file_path in chat_dir.rglob('*'):
                   if file_path.is_file():
                       # Skip node_modules and dist directories
                       if 'node_modules' in file_path.parts or 'dist' in file_path.parts:
                           continue

                       # Store as web-component/* (CodeBuild expects this structure)
                       arcname = Path('web-component') / file_path.relative_to(chat_dir)
                       zipf.write(file_path, arcname)

           log_success(f"Web component source packaged: {zip_path}")

           # Upload to S3
           s3_client = boto3.client('s3', region_name=region)

           # Upload with timestamp-based key
           timestamp = int(time.time())
           key = f'web-component-source-{timestamp}.zip'

           log_info(f"Uploading to s3://{bucket_name}/{key}...")
           try:
               s3_client.upload_file(zip_path, bucket_name, key)
               log_success("Web component source uploaded to S3")
           except ClientError as e:
               raise IOError(f"Failed to upload web component source to S3: {e}") from e

           # Clean up temporary file
           os.remove(zip_path)

           return key

       except (FileNotFoundError, IOError):
           # Re-raise expected exceptions
           if os.path.exists(zip_path):
               os.remove(zip_path)
           raise
       except Exception as e:
           # Clean up temporary file on unexpected error
           if os.path.exists(zip_path):
               os.remove(zip_path)
           raise IOError(f"Unexpected error packaging web component source: {e}") from e
   ```

3. **Verify the function:**
   - Matches `package_ui_source()` pattern (same error handling, logging)
   - Uses `web-component/` prefix in zip (not `amplify-chat/`)
   - Excludes `node_modules` and `dist`
   - Returns S3 key for use in Phase 3

### Verification Checklist

- [ ] Function signature matches doc comment
- [ ] Excludes `node_modules` and `dist` directories
- [ ] Zip structure is `web-component/package.json`, `web-component/src/...`
- [ ] Error handling matches `package_ui_source()` pattern
- [ ] Logging uses existing `log_info()`, `log_success()` helpers
- [ ] Returns S3 key string
- [ ] Cleans up temp file in all code paths

### Testing

Create `tests/test_package_amplify_chat.py`:

```python
"""Tests for web component source packaging."""
import pytest
import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from publish import package_amplify_chat_source


def test_package_creates_zip_with_correct_structure(tmp_path):
    """Verify zip contains web-component/* structure."""
    # Create mock src/amplify-chat directory
    chat_dir = tmp_path / 'src' / 'amplify-chat'
    chat_dir.mkdir(parents=True)

    # Create test files
    (chat_dir / 'package.json').write_text('{}')
    (chat_dir / 'src').mkdir()
    (chat_dir / 'src' / 'index.ts').write_text('export {}')

    # Create node_modules (should be excluded)
    (chat_dir / 'node_modules').mkdir()
    (chat_dir / 'node_modules' / 'pkg').mkdir()
    (chat_dir / 'node_modules' / 'pkg' / 'index.js').write_text('')

    with patch('publish.Path.cwd', return_value=tmp_path):
        with patch('publish.boto3.client') as mock_s3:
            # Mock S3 upload
            mock_client = MagicMock()
            mock_s3.return_value = mock_client

            # Call function
            key = package_amplify_chat_source('test-bucket', 'us-east-1')

            # Verify S3 upload was called
            assert mock_client.upload_file.called
            zip_path = mock_client.upload_file.call_args[0][0]

            # Verify zip contents
            with zipfile.ZipFile(zip_path, 'r') as zf:
                names = zf.namelist()

                # Should have web-component prefix
                assert 'web-component/package.json' in names
                assert 'web-component/src/index.ts' in names

                # Should NOT have node_modules
                assert not any('node_modules' in n for n in names)


def test_package_raises_if_directory_missing():
    """Verify error when src/amplify-chat doesn't exist."""
    with pytest.raises(FileNotFoundError) as exc_info:
        package_amplify_chat_source('test-bucket', 'us-east-1')

    assert 'Web component directory not found' in str(exc_info.value)


def test_package_returns_s3_key():
    """Verify function returns S3 key with timestamp."""
    with patch('publish.Path') as mock_path:
        # Mock directory exists
        mock_chat_dir = MagicMock()
        mock_chat_dir.exists.return_value = True
        mock_chat_dir.rglob.return_value = []
        mock_path.return_value = mock_chat_dir

        with patch('publish.boto3.client') as mock_s3:
            mock_client = MagicMock()
            mock_s3.return_value = mock_client

            with patch('publish.time.time', return_value=1234567890):
                key = package_amplify_chat_source('test-bucket', 'us-east-1')

                assert key == 'web-component-source-1234567890.zip'
```

Run tests:
```bash
pytest tests/test_package_amplify_chat.py -v
```

### Commit

```bash
git add publish.py tests/test_package_amplify_chat.py
git commit -m "feat(publish): add package_amplify_chat_source function

- Package src/amplify-chat/ to zip for CodeBuild deployment
- Exclude node_modules and dist directories
- Use web-component/ prefix in zip structure
- Match existing package_ui_source pattern
- Include unit tests for packaging logic"
```

---

## Task 3: Add Detection Flag for Chat Deployment

### Goal

Modify `seed_configuration_table()` to add a `chat_deployed` field when the `--deploy-chat` flag will be used (Phase 5's UI uses this to show/hide chat settings).

### Files to Modify

- `publish.py` (modify `seed_configuration_table()` signature and logic)

### Background

Phase 5's SAM UI needs to know if chat is deployed to conditionally show the chat settings section. We'll add a boolean flag to the Default configuration.

**Note:** For now, we'll always set `chat_deployed: False` in the seeding. Phase 3 will update this to `True` when Amplify is actually deployed.

### Instructions

1. **Modify seed_configuration_table() signature:**

   Change:
   ```python
   def seed_configuration_table(stack_name, region):
   ```

   To:
   ```python
   def seed_configuration_table(stack_name, region, chat_deployed=False):
   ```

2. **Add chat_deployed to default_item:**

   In the `default_item` dictionary, add at the top (after `'Configuration': 'Default'`):

   ```python
   'chat_deployed': chat_deployed,
   ```

3. **Update docstring:**

   Add parameter documentation:
   ```python
   """
   Seed ConfigurationTable with Schema and Default configurations.

   Args:
       stack_name: CloudFormation stack name
       region: AWS region
       chat_deployed: Whether Amplify chat is deployed (default False)
   """
   ```

4. **Verify existing call sites:**

   Search for `seed_configuration_table(` in `publish.py` to find where it's called. There should be one call in `main()` around line 1150:

   ```python
   seed_configuration_table(stack_name, args.region)
   ```

   This is correct - defaults to `chat_deployed=False`. Phase 3 will change this call.

### Verification Checklist

- [ ] Function signature includes `chat_deployed=False` parameter
- [ ] Docstring documents the parameter
- [ ] `default_item` includes `'chat_deployed': chat_deployed`
- [ ] Existing call in `main()` unchanged (uses default)
- [ ] No syntax errors

### Testing

Add to `tests/test_seed_configuration.py`:

```python
def test_chat_deployed_flag_default():
    """Verify chat_deployed defaults to False."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call without chat_deployed argument
            seed_configuration_table('test-stack', 'us-east-1')

            calls = mock_table.put_item.call_args_list
            default_item = calls[1][1]['Item']

            assert default_item['chat_deployed'] is False


def test_chat_deployed_flag_true():
    """Verify chat_deployed can be set to True."""
    mock_table = MagicMock()

    with patch('publish.boto3.resource') as mock_resource:
        with patch('publish.boto3.client') as mock_client:
            mock_cfn = MagicMock()
            mock_cfn.describe_stacks.return_value = {
                'Stacks': [{
                    'Outputs': [{
                        'OutputKey': 'ConfigurationTableName',
                        'OutputValue': 'test-table'
                    }]
                }]
            }
            mock_client.return_value = mock_cfn

            mock_dynamodb = MagicMock()
            mock_dynamodb.Table.return_value = mock_table
            mock_resource.return_value = mock_dynamodb

            # Call with chat_deployed=True
            seed_configuration_table('test-stack', 'us-east-1', chat_deployed=True)

            calls = mock_table.put_item.call_args_list
            default_item = calls[1][1]['Item']

            assert default_item['chat_deployed'] is True
```

Run tests:
```bash
pytest tests/test_seed_configuration.py::test_chat_deployed_flag_default -v
pytest tests/test_seed_configuration.py::test_chat_deployed_flag_true -v
```

### Commit

```bash
git add publish.py tests/test_seed_configuration.py
git commit -m "feat(config): add chat_deployed flag to ConfigurationTable

- Add chat_deployed parameter to seed_configuration_table
- Defaults to False (UI hides chat section until deployed)
- Phase 3 will set to True when Amplify deployed
- Include unit tests for flag behavior"
```

---

## Phase 1 Complete - Verification

Before moving to Phase 2, verify:

### Checklist

- [ ] All commits made with conventional commit format
- [ ] All unit tests pass: `pytest tests/test_seed_configuration.py tests/test_package_amplify_chat.py -v`
- [ ] No syntax errors: `python -m py_compile publish.py`
- [ ] Schema has 7 new chat fields with correct defaults
- [ ] `package_amplify_chat_source()` function exists and follows existing pattern
- [ ] `chat_deployed` flag added to seeding logic

### Run Full Test Suite

```bash
# All new tests
pytest tests/test_seed_configuration.py tests/test_package_amplify_chat.py -v --cov=publish

# Verify no regressions in existing tests
pytest tests/ -v
```

### Manual Verification

While we can't deploy yet (Amplify infrastructure not ready), verify the code compiles:

```bash
python -c "from publish import seed_configuration_table, package_amplify_chat_source; print('Import successful')"
```

---

## Common Issues

**Issue:** `ModuleNotFoundError: No module named 'boto3'`
- **Solution:** Run `uv pip install -r requirements.txt`

**Issue:** Tests fail with "src/amplify-chat not found"
- **Solution:** Tests use mocking, check patch decorators are correct

**Issue:** Zip structure wrong (amplify-chat/* instead of web-component/*)
- **Solution:** Verify `arcname = Path('web-component') / ...` in packaging code

---

## Handoff to Phase 2

**What you've delivered:**
- ✅ ConfigurationTable schema extended (contract for Phase 4, 5)
- ✅ Web component packaging function ready (contract for Phase 3)
- ✅ Detection flag for UI conditional rendering

**What Phase 2 will do:**
- Build the actual web component in `src/amplify-chat/`
- Create React component, web component wrapper, build config
- Ensure package structure matches what `package_amplify_chat_source()` expects

---

**Next:** [Phase-2.md](Phase-2.md) - Web Component Implementation
