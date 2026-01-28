# Vulture whitelist for pytest fixtures and Lambda patterns
# These names are used by pytest/AWS but not explicitly referenced in code

# Lambda entry points (always called by AWS, never by code)
handler
lambda_handler

# Re-exports for test access (imported by tests from Lambda modules)
construct_image_uri_from_content_uri

# CloudFormation custom resource helper decorators (crhelper)
# These functions are invoked by the CfnResource framework via decorator registration
create_or_update  # @helper.create and @helper.update
poll_create_or_update  # @helper.poll_create and @helper.poll_update
delete  # @helper.delete

# Pytest fixtures (injected by pytest, not direct calls)
# Configuration resolver test fixtures
mock_env  # pytest fixture that sets environment variables
mock_config
mock_bedrock
mock_s3
mock_dynamodb
sample_metadata
sample_document
mock_env_with_key_library
set_env_vars

# Fixtures from tests/conftest.py
pytest_configure  # pytest hook
sample_key_library_entries
sample_immigration_text
sample_census_text
sample_genealogy_text
sample_image_caption
immigration_metadata

# Common pytest patterns
request  # pytest fixture parameter
tmp_path  # pytest built-in fixture
monkeypatch  # pytest built-in fixture
capsys  # pytest built-in fixture
caplog  # pytest built-in fixture for log capture
mocker  # pytest-mock fixture

# Mock attributes (set dynamically in tests)
side_effect

# Test function keyword arguments captured but unused
kw

# API compatibility parameters (passed by callers but implementation simplified)
min_per_slice  # merge_slices_with_guaranteed_minimum - kept for API compatibility
