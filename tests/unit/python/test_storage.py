"""Unit tests for storage utilities."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ragstack_common.exceptions import FileSizeLimitExceededError
from ragstack_common.storage import parse_s3_uri, read_s3_binary


class TestParseS3Uri:
    def test_standard_uri(self):
        bucket, key = parse_s3_uri("s3://my-bucket/path/to/file.pdf")
        assert bucket == "my-bucket"
        assert key == "path/to/file.pdf"

    def test_root_uri(self):
        bucket, key = parse_s3_uri("s3://my-bucket/")
        assert bucket == "my-bucket"
        assert key == ""

    def test_https_format(self):
        url = "https://s3.us-east-1.amazonaws.com/my-bucket/transcripts/doc-id/file.json"
        bucket, key = parse_s3_uri(url)
        assert bucket == "my-bucket"
        assert key == "transcripts/doc-id/file.json"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty or None"):
            parse_s3_uri("")

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid S3 URI"):
            parse_s3_uri("https://example.com/file.txt")


class TestReadS3Binary:
    @patch("ragstack_common.storage.get_s3_client")
    def test_no_max_size_skips_head(self, mock_get_client):
        """When max_size_bytes is None, no HEAD call is made."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_body = MagicMock()
        mock_body.read.return_value = b"file content"
        mock_client.get_object.return_value = {"Body": mock_body}

        result = read_s3_binary("s3://bucket/key.bin")

        assert result == b"file content"
        mock_client.head_object.assert_not_called()
        mock_client.get_object.assert_called_once_with(Bucket="bucket", Key="key.bin")

    @patch("ragstack_common.storage.get_s3_client")
    def test_under_max_size_succeeds(self, mock_get_client):
        """File under max_size_bytes downloads normally."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.head_object.return_value = {"ContentLength": 500}
        mock_body = MagicMock()
        mock_body.read.return_value = b"x" * 500
        mock_client.get_object.return_value = {"Body": mock_body}

        result = read_s3_binary("s3://bucket/key.bin", max_size_bytes=1000)

        assert len(result) == 500
        mock_client.head_object.assert_called_once_with(Bucket="bucket", Key="key.bin")

    @patch("ragstack_common.storage.get_s3_client")
    def test_over_max_size_raises(self, mock_get_client):
        """File over max_size_bytes raises FileSizeLimitExceededError."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.head_object.return_value = {"ContentLength": 2000}

        with pytest.raises(FileSizeLimitExceededError) as exc_info:
            read_s3_binary("s3://bucket/key.bin", max_size_bytes=1000)

        assert exc_info.value.actual_size == 2000
        assert exc_info.value.max_size == 1000
        assert "s3://bucket/key.bin" in str(exc_info.value)
        # Should NOT call get_object when over limit
        mock_client.get_object.assert_not_called()

    @patch("ragstack_common.storage.get_s3_client")
    def test_head_failure_raises(self, mock_get_client):
        """If HEAD fails with max_size_bytes set, raise ClientError (fail closed)."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadObject"
        )

        with pytest.raises(ClientError):
            read_s3_binary("s3://bucket/key.bin", max_size_bytes=1000)

        # Should NOT proceed to GET when HEAD fails and size guard is active
        mock_client.get_object.assert_not_called()
