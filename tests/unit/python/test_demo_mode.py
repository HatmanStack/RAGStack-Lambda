"""Unit tests for demo mode functionality.

Tests the demo mode utilities in lib/ragstack_common/demo_mode.py.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ragstack_common.demo_mode import (
    DemoModeError,
    check_demo_mode_feature_allowed,
    demo_quota_check_and_increment,
    is_demo_mode_enabled,
)


class TestIsDemoModeEnabled:
    """Tests for is_demo_mode_enabled function."""

    def test_enabled_via_env_var(self):
        """Demo mode enabled when DEMO_MODE=true."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            assert is_demo_mode_enabled() is True

    def test_enabled_via_env_var_uppercase(self):
        """Demo mode enabled when DEMO_MODE=TRUE (case insensitive)."""
        with patch.dict(os.environ, {"DEMO_MODE": "TRUE"}):
            assert is_demo_mode_enabled() is True

    def test_disabled_by_default(self):
        """Demo mode disabled when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_demo_mode_enabled() is False

    def test_disabled_when_false(self):
        """Demo mode disabled when DEMO_MODE=false."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            assert is_demo_mode_enabled() is False

    def test_enabled_via_config_manager(self):
        """Demo mode enabled via config manager when env not set."""
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = True

        with patch.dict(os.environ, {}, clear=True):
            assert is_demo_mode_enabled(mock_config) is True
            mock_config.get_parameter.assert_called_with("demo_mode_enabled", False)

    def test_env_takes_precedence_over_config(self):
        """Env var takes precedence over config manager."""
        mock_config = MagicMock()
        mock_config.get_parameter.return_value = False

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            # Env var is true, config says false - env wins
            assert is_demo_mode_enabled(mock_config) is True


class TestCheckDemoModeFeatureAllowed:
    """Tests for check_demo_mode_feature_allowed function."""

    def test_allows_feature_when_demo_mode_disabled(self):
        """Features allowed when demo mode is disabled."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            # Should not raise for any feature
            check_demo_mode_feature_allowed("reindex_all")
            check_demo_mode_feature_allowed("reprocess")
            check_demo_mode_feature_allowed("delete_documents")

    def test_blocks_reindex_in_demo_mode(self):
        """Reindex blocked when demo mode enabled."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            with pytest.raises(DemoModeError) as exc:
                check_demo_mode_feature_allowed("reindex_all")
            assert "Reindex All Documents" in str(exc.value)
            assert exc.value.feature == "reindex_all"

    def test_blocks_reprocess_in_demo_mode(self):
        """Reprocess blocked when demo mode enabled."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            with pytest.raises(DemoModeError) as exc:
                check_demo_mode_feature_allowed("reprocess")
            assert "Reprocess Document" in str(exc.value)
            assert exc.value.feature == "reprocess"

    def test_blocks_delete_in_demo_mode(self):
        """Delete blocked when demo mode enabled."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            with pytest.raises(DemoModeError) as exc:
                check_demo_mode_feature_allowed("delete_documents")
            assert "Delete Documents" in str(exc.value)
            assert exc.value.feature == "delete_documents"

    def test_allows_other_features_in_demo_mode(self):
        """Other features allowed in demo mode."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            # These should not raise
            check_demo_mode_feature_allowed("upload")
            check_demo_mode_feature_allowed("query")
            check_demo_mode_feature_allowed("some_other_feature")


class TestDemoQuotaCheckAndIncrement:
    """Tests for demo_quota_check_and_increment function."""

    @pytest.fixture
    def mock_dynamodb_client(self):
        """Create a mock DynamoDB client."""
        return MagicMock()

    @pytest.fixture
    def mock_config_manager(self):
        """Create a mock config manager."""
        mock = MagicMock()
        mock.get_parameter.side_effect = lambda key, default=None: {
            "demo_upload_quota_daily": 5,
            "demo_chat_quota_daily": 30,
        }.get(key, default)
        return mock

    def test_allows_when_demo_mode_disabled(self, mock_dynamodb_client):
        """Always allows when demo mode is disabled."""
        with patch.dict(os.environ, {"DEMO_MODE": "false"}):
            allowed, message = demo_quota_check_and_increment(
                "user123", "upload", "config-table", mock_dynamodb_client
            )
            assert allowed is True
            assert message == ""
            # Should not call DynamoDB when demo mode disabled
            mock_dynamodb_client.transact_write_items.assert_not_called()

    def test_requires_user_id_in_demo_mode(self, mock_dynamodb_client, mock_config_manager):
        """Requires user ID in demo mode."""
        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            allowed, message = demo_quota_check_and_increment(
                None, "upload", "config-table", mock_dynamodb_client, mock_config_manager
            )
            assert allowed is False
            assert "Authentication required" in message

    def test_increments_quota_on_success(self, mock_dynamodb_client, mock_config_manager):
        """Increments quota and returns True when within limit."""
        mock_dynamodb_client.transact_write_items.return_value = {}

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            allowed, message = demo_quota_check_and_increment(
                "user123", "upload", "config-table", mock_dynamodb_client, mock_config_manager
            )

            assert allowed is True
            assert message == ""
            mock_dynamodb_client.transact_write_items.assert_called_once()

    def test_returns_false_when_quota_exceeded(self, mock_dynamodb_client, mock_config_manager):
        """Returns False when quota is exceeded."""
        # Simulate TransactionCanceledException from condition check failure
        error_response = {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            }
        }
        mock_dynamodb_client.transact_write_items.side_effect = ClientError(
            error_response, "TransactWriteItems"
        )

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            allowed, message = demo_quota_check_and_increment(
                "user123", "upload", "config-table", mock_dynamodb_client, mock_config_manager
            )

            assert allowed is False
            assert "limit reached" in message.lower()
            assert "5" in message  # Upload limit

    def test_chat_quota_uses_chat_limit(self, mock_dynamodb_client, mock_config_manager):
        """Chat quota type uses chat limit from config."""
        error_response = {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            }
        }
        mock_dynamodb_client.transact_write_items.side_effect = ClientError(
            error_response, "TransactWriteItems"
        )

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            allowed, message = demo_quota_check_and_increment(
                "user123", "chat", "config-table", mock_dynamodb_client, mock_config_manager
            )

            assert allowed is False
            assert "30" in message  # Chat limit

    def test_uses_default_limit_without_config(self, mock_dynamodb_client):
        """Uses default limit when config manager not provided."""
        error_response = {
            "Error": {
                "Code": "TransactionCanceledException",
                "Message": "Transaction cancelled",
            }
        }
        mock_dynamodb_client.transact_write_items.side_effect = ClientError(
            error_response, "TransactWriteItems"
        )

        with patch.dict(os.environ, {"DEMO_MODE": "true"}):
            allowed, message = demo_quota_check_and_increment(
                "user123", "upload", "config-table", mock_dynamodb_client, None
            )

            assert allowed is False
            assert "5" in message  # Default upload limit


class TestDemoModeError:
    """Tests for DemoModeError exception."""

    def test_error_attributes(self):
        """Error has message and feature attributes."""
        error = DemoModeError("Test message", "test_feature")
        assert error.message == "Test message"
        assert error.feature == "test_feature"
        assert str(error) == "Test message"
