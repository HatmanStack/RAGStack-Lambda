# Vulture whitelist for pytest fixtures and Lambda patterns
# These names are used by pytest/AWS but not explicitly referenced in code

# Lambda entry points (always called by AWS, never by code)
handler
lambda_handler

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

# Common pytest patterns
request  # pytest fixture parameter
tmp_path  # pytest built-in fixture
monkeypatch  # pytest built-in fixture
capsys  # pytest built-in fixture
caplog  # pytest built-in fixture for log capture
mocker  # pytest-mock fixture

# Test function keyword arguments captured but unused
kw
