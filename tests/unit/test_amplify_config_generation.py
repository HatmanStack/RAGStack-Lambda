"""
Unit tests for Amplify config generation in publish.py

Tests the automatic generation of amplify/data/config.ts with Knowledge Base ID.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestWriteAmplifyConfig:
    """Test amplify config generation."""

    def test_write_amplify_config_creates_file(self):
        """Test that config file is created with correct content."""
        from publish import write_amplify_config

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create amplify/data directory structure
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            # Write config
            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                write_amplify_config(
                    "test-kb-12345",
                    "us-east-1",
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                # Verify file exists
                config_file = config_dir / "config.ts"
                assert config_file.exists(), "Config file was not created"

                # Verify content
                content = config_file.read_text()
                assert "test-kb-12345" in content
                assert "us-east-1" in content
                assert "KNOWLEDGE_BASE_CONFIG" in content
                assert "export const" in content
            finally:
                import os

                os.chdir(original_cwd)

    def test_write_amplify_config_kb_id_in_config(self):
        """Test that Knowledge Base ID is correctly placed in config."""
        from publish import write_amplify_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                kb_id = "ABC123DEF456"
                write_amplify_config(
                    kb_id,
                    "us-west-2",
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                config_file = config_dir / "config.ts"
                content = config_file.read_text()

                # Verify KB ID is assigned to knowledgeBaseId
                assert f'knowledgeBaseId: "{kb_id}"' in content
            finally:
                import os

                os.chdir(original_cwd)

    def test_write_amplify_config_region_in_config(self):
        """Test that region is correctly placed in config."""
        from publish import write_amplify_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                region = "eu-west-1"
                write_amplify_config(
                    "test-kb-id",
                    region,
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                config_file = config_dir / "config.ts"
                content = config_file.read_text()

                # Verify region is assigned
                assert f'region: "{region}"' in content
            finally:
                import os

                os.chdir(original_cwd)

    def test_write_amplify_config_is_typescript(self):
        """Test that generated config is valid TypeScript."""
        from publish import write_amplify_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                write_amplify_config(
                    "test-kb-id",
                    "us-east-1",
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                config_file = config_dir / "config.ts"
                content = config_file.read_text()

                # Verify TypeScript syntax
                assert "export const KNOWLEDGE_BASE_CONFIG" in content
                assert "as const" in content
                assert "export type KnowledgeBaseConfig" in content
            finally:
                import os

                os.chdir(original_cwd)


class TestExtractKnowledgeBaseId:
    """Test extraction of KB ID from SAM stack outputs."""

    @patch("publish.boto3")
    def test_extract_knowledge_base_id_success(self, mock_boto3):
        """Test successful KB ID extraction from stack outputs."""
        from publish import extract_knowledge_base_id

        # Mock CloudFormation response
        mock_cf = MagicMock()
        mock_boto3.client.return_value = mock_cf

        mock_cf.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "KnowledgeBaseId", "OutputValue": "kb-xyz-789"},
                        {"OutputKey": "OtherOutput", "OutputValue": "some-value"},
                    ]
                }
            ]
        }

        kb_id = extract_knowledge_base_id("RAGStack-myproject", "us-east-1")

        assert kb_id == "kb-xyz-789"
        mock_boto3.client.assert_called_with("cloudformation", region_name="us-east-1")

    @patch("publish.boto3")
    def test_extract_knowledge_base_id_not_found(self, mock_boto3):
        """Test error when KB ID not found in outputs."""
        from publish import extract_knowledge_base_id

        mock_cf = MagicMock()
        mock_boto3.client.return_value = mock_cf

        mock_cf.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "SomeOtherOutput", "OutputValue": "value"},
                    ]
                }
            ]
        }

        with pytest.raises(ValueError) as exc_info:
            extract_knowledge_base_id("RAGStack-myproject", "us-east-1")

        assert "KnowledgeBaseId not found" in str(exc_info.value)

    @patch("publish.boto3")
    def test_extract_knowledge_base_id_empty_outputs(self, mock_boto3):
        """Test error when stack has no outputs."""
        from publish import extract_knowledge_base_id

        mock_cf = MagicMock()
        mock_boto3.client.return_value = mock_cf

        mock_cf.describe_stacks.return_value = {"Stacks": [{"Outputs": []}]}

        with pytest.raises(ValueError):
            extract_knowledge_base_id("RAGStack-myproject", "us-east-1")


class TestPublishPyIntegration:
    """Integration tests for publish.py with config generation."""

    @patch("publish.boto3")
    @patch("publish.run_command")
    def test_chat_only_deployment_flow(self, _mock_run_cmd, mock_boto3):
        """Test chat-only deployment including config generation."""
        from publish import extract_knowledge_base_id, write_amplify_config

        # Mock CloudFormation
        mock_cf = MagicMock()
        mock_boto3.client.return_value = mock_cf
        mock_cf.describe_stacks.return_value = {
            "Stacks": [
                {
                    "Outputs": [
                        {"OutputKey": "KnowledgeBaseId", "OutputValue": "test-kb-id-123"},
                    ]
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                # Simulate chat-only flow
                kb_id = extract_knowledge_base_id("RAGStack-test", "us-east-1")
                assert kb_id == "test-kb-id-123"

                write_amplify_config(
                    kb_id,
                    "us-east-1",
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                # Verify config was created
                config_file = config_dir / "config.ts"
                assert config_file.exists()
                content = config_file.read_text()
                assert "test-kb-id-123" in content
            finally:
                import os

                os.chdir(original_cwd)


class TestConfigFileTypes:
    """Test config file TypeScript types."""

    def test_config_exports_type(self):
        """Test that config exports proper TypeScript type."""
        from publish import write_amplify_config

        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "amplify" / "data"
            config_dir.mkdir(parents=True, exist_ok=True)

            original_cwd = Path.cwd()
            try:
                import os

                os.chdir(tmpdir)

                write_amplify_config(
                    "kb-id",
                    "us-east-1",
                    "test-config-table",
                    "test-bucket",
                    "test-key",
                    "test-pool-id",
                    "test-client-id",
                )

                config_file = config_dir / "config.ts"
                content = config_file.read_text()

                # Verify type definition exists
                assert "export type KnowledgeBaseConfig" in content
                assert "typeof KNOWLEDGE_BASE_CONFIG" in content
            finally:
                import os

                os.chdir(original_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
