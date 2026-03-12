"""Unit tests for start_codebuild Lambda."""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def _ensure_crhelper_mock():
    """Ensure crhelper is available (mock it if not installed)."""
    if "crhelper" not in sys.modules:
        mock_crhelper = MagicMock()
        # CfnResource needs to return an object with decorator methods
        mock_cfn = MagicMock()
        mock_cfn.create = lambda f: f
        mock_cfn.update = lambda f: f
        mock_cfn.delete = lambda f: f
        mock_cfn.poll_create = lambda f: f
        mock_cfn.poll_update = lambda f: f
        mock_crhelper.CfnResource.return_value = mock_cfn
        sys.modules["crhelper"] = mock_crhelper


def load_start_codebuild_module():
    """Load the start_codebuild index module dynamically."""
    _ensure_crhelper_mock()

    module_path = (
        Path(__file__).parent.parent.parent.parent
        / "src" / "lambda" / "start_codebuild" / "index.py"
    ).resolve()

    if "start_codebuild_index" in sys.modules:
        del sys.modules["start_codebuild_index"]

    spec = importlib.util.spec_from_file_location("start_codebuild_index", str(module_path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["start_codebuild_index"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def set_env_vars():
    with patch.dict(os.environ, {"AWS_REGION": "us-east-1"}):
        yield


class TestRedactEvent:
    """Tests for _redact_event function."""

    @patch("boto3.client")
    def test_redacts_sensitive_fields(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_start_codebuild_module()

        event = {
            "RequestType": "Create",
            "ResourceProperties": {"secret": "value"},
            "ResponseURL": "https://example.com",
            "ServiceToken": "arn:aws:lambda:...",
            "StackId": "arn:aws:cloudformation:...",
        }
        result = module._redact_event(event)
        assert result["ResourceProperties"] == "***redacted***"
        assert result["ResponseURL"] == "***redacted***"
        assert result["ServiceToken"] == "***redacted***"
        assert result["StackId"] == "arn:aws:cloudformation:..."

    @patch("boto3.client")
    def test_non_dict_returns_redacted(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_start_codebuild_module()

        assert module._redact_event("not a dict") == "***non-dict***"


class TestCreateOrUpdate:
    """Tests for create_or_update function."""

    @patch("boto3.client")
    def test_starts_build_happy_path(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.start_build.return_value = {
            "build": {"id": "project:build-123"}
        }
        mock_codebuild.meta.region_name = "us-east-1"
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with patch.object(module, "codebuild_client", mock_codebuild):
            event = {
                "RequestType": "Create",
                "RequestId": "req-123",
                "ResourceProperties": {"BuildProjectName": "my-project"},
            }
            module.create_or_update(event, None)

        mock_codebuild.start_build.assert_called_once()
        call_kwargs = mock_codebuild.start_build.call_args[1]
        assert call_kwargs["projectName"] == "my-project"

    @patch("boto3.client")
    def test_missing_project_name_raises(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_start_codebuild_module()

        event = {
            "RequestType": "Create",
            "RequestId": "req-123",
            "ResourceProperties": {},
        }
        with pytest.raises(ValueError, match="BuildProjectName"):
            module.create_or_update(event, None)

    @patch("boto3.client")
    def test_source_location_override(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.start_build.return_value = {
            "build": {"id": "project:build-456"}
        }
        mock_codebuild.meta.region_name = "us-east-1"
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with patch.object(module, "codebuild_client", mock_codebuild):
            event = {
                "RequestType": "Create",
                "RequestId": "req-123",
                "ResourceProperties": {
                    "BuildProjectName": "my-project",
                    "SourceLocationOverride": "s3://bucket/source.zip",
                },
            }
            module.create_or_update(event, None)

        call_kwargs = mock_codebuild.start_build.call_args[1]
        assert call_kwargs["sourceLocationOverride"] == "s3://bucket/source.zip"

    @patch("boto3.client")
    def test_start_build_failure_raises(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.start_build.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Project not found"}},
            "StartBuild",
        )
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with (
            patch.object(module, "codebuild_client", mock_codebuild),
            pytest.raises(ClientError),
        ):
            event = {
                "RequestType": "Create",
                "RequestId": "req-123",
                "ResourceProperties": {"BuildProjectName": "missing-project"},
            }
            module.create_or_update(event, None)


class TestPollCreateOrUpdate:
    """Tests for poll_create_or_update function."""

    @patch("boto3.client")
    def test_build_succeeded(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.batch_get_builds.return_value = {
            "builds": [{"buildStatus": "SUCCEEDED"}]
        }
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with patch.object(module, "codebuild_client", mock_codebuild):
            result = module.poll_create_or_update(
                {"CrHelperData": {"build_id": "project:build-123"}}, None
            )
        assert result is True

    @patch("boto3.client")
    def test_build_in_progress(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.batch_get_builds.return_value = {
            "builds": [{"buildStatus": "IN_PROGRESS"}]
        }
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with patch.object(module, "codebuild_client", mock_codebuild):
            result = module.poll_create_or_update(
                {"CrHelperData": {"build_id": "project:build-123"}}, None
            )
        assert result is None

    @patch("boto3.client")
    def test_build_failed_raises(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.batch_get_builds.return_value = {
            "builds": [{"buildStatus": "FAILED"}]
        }
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with (
            patch.object(module, "codebuild_client", mock_codebuild),
            pytest.raises(RuntimeError, match="FAILED"),
        ):
            module.poll_create_or_update(
                {"CrHelperData": {"build_id": "project:build-123"}}, None
            )

    @patch("boto3.client")
    def test_missing_build_id_raises(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()
        module = load_start_codebuild_module()

        with pytest.raises(ValueError, match="build_id"):
            module.poll_create_or_update({"CrHelperData": {}}, None)

    @patch("boto3.client")
    def test_build_not_found_raises(self, mock_boto3_client):
        mock_codebuild = MagicMock()
        mock_codebuild.batch_get_builds.return_value = {
            "builds": [],
            "buildsNotFound": ["project:build-missing"],
        }
        mock_boto3_client.return_value = mock_codebuild

        module = load_start_codebuild_module()
        with (
            patch.object(module, "codebuild_client", mock_codebuild),
            pytest.raises(RuntimeError, match="not found"),
        ):
            module.poll_create_or_update(
                {"CrHelperData": {"build_id": "project:build-missing"}}, None
            )
