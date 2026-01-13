"""Unit tests for NovaEmbeddingsClient."""

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from ragstack_common.nova_embeddings import NovaEmbeddingsClient


class TestNovaEmbeddingsClientInit:
    """Tests for NovaEmbeddingsClient initialization."""

    @patch("boto3.client")
    def test_creates_bedrock_runtime_client_on_access(self, mock_boto3_client):
        """Test that NovaEmbeddingsClient creates bedrock-runtime client on first access."""
        mock_boto3_client.return_value = MagicMock()
        client = NovaEmbeddingsClient()
        # Client is lazy-loaded, not created until accessed
        _ = client.bedrock_client
        mock_boto3_client.assert_called_once()
        assert "bedrock-runtime" in str(mock_boto3_client.call_args)

    @patch("boto3.client")
    def test_accepts_custom_region(self, mock_boto3_client):
        """Test that custom region is passed to boto3."""
        mock_boto3_client.return_value = MagicMock()
        client = NovaEmbeddingsClient(region="us-west-2")
        # Access the property to trigger client creation
        _ = client.bedrock_client
        call_args = mock_boto3_client.call_args
        assert call_args.kwargs.get("region_name") == "us-west-2"

    @patch("boto3.client")
    def test_default_embedding_dimension(self, mock_boto3_client):
        """Test default embedding dimension is 1024."""
        mock_boto3_client.return_value = MagicMock()
        client = NovaEmbeddingsClient()
        assert client.embedding_dimension == 1024

    @patch("boto3.client")
    def test_custom_embedding_dimension(self, mock_boto3_client):
        """Test custom embedding dimension is accepted."""
        mock_boto3_client.return_value = MagicMock()
        client = NovaEmbeddingsClient(embedding_dimension=512)
        assert client.embedding_dimension == 512


class TestEmbedVideoSegment:
    """Tests for video segment embedding."""

    @patch("boto3.client")
    def test_embed_video_segment_returns_vector(self, mock_boto3_client):
        """Test that embed_video_segment returns embedding vector."""
        mock_client = MagicMock()
        # Nova embeddings response format
        mock_response = {
            "embedding": [0.1] * 1024,
            "inputTextTokenCount": 0,
        }
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()
        video_bytes = b"fake video content"
        result = client.embed_video_segment(video_bytes)

        assert "embedding" in result
        assert len(result["embedding"]) == 1024
        mock_client.invoke_model.assert_called_once()

    @patch("boto3.client")
    def test_embed_video_segment_uses_correct_model(self, mock_boto3_client):
        """Test that Nova Multimodal Embeddings model is used."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.1] * 1024}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()
        client.embed_video_segment(b"fake video")

        call_args = mock_client.invoke_model.call_args
        model_id = call_args.kwargs.get("modelId", call_args.args[0] if call_args.args else None)
        assert "amazon.nova" in model_id.lower() or "embed" in model_id.lower()

    @patch("boto3.client")
    def test_embed_video_segment_encodes_base64(self, mock_boto3_client):
        """Test that video content is base64 encoded in request."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.1] * 1024}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()
        video_bytes = b"test video content"
        client.embed_video_segment(video_bytes)

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", "{}"))

        # Should have inputVideo with base64 content
        assert "inputVideo" in body or "inputs" in body


class TestEmbedAudioSegment:
    """Tests for audio segment embedding."""

    @patch("boto3.client")
    def test_embed_audio_segment_returns_vector(self, mock_boto3_client):
        """Test that embed_audio_segment returns embedding vector."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.2] * 1024}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()
        audio_bytes = b"fake audio content"
        result = client.embed_audio_segment(audio_bytes)

        assert "embedding" in result
        assert len(result["embedding"]) == 1024

    @patch("boto3.client")
    def test_embed_audio_segment_uses_correct_content_type(self, mock_boto3_client):
        """Test that audio content type is specified."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.2] * 1024}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()
        client.embed_audio_segment(b"audio data")

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", "{}"))

        # Should specify audio content
        assert "inputAudio" in body or "inputs" in body


class TestEmbedFromS3:
    """Tests for S3-based embedding (async mode)."""

    @patch("boto3.client")
    def test_embed_from_s3_uri(self, mock_boto3_client):
        """Test embedding from S3 URI."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.3] * 1024}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        # Also mock S3 client for getting object
        mock_s3_client = MagicMock()
        mock_s3_client.get_object.return_value = {"Body": MagicMock(read=lambda: b"video content")}

        def client_factory(service_name, **kwargs):
            if service_name == "bedrock-runtime":
                return mock_client
            if service_name == "s3":
                return mock_s3_client
            return MagicMock()

        mock_boto3_client.side_effect = client_factory

        client = NovaEmbeddingsClient()
        result = client.embed_from_s3("s3://bucket/video.mp4", media_type="video")

        assert "embedding" in result


class TestEmbeddingDimension:
    """Tests for embedding dimension configuration."""

    @patch("boto3.client")
    def test_dimension_in_request(self, mock_boto3_client):
        """Test that embedding dimension is passed in request."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.1] * 512}
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient(embedding_dimension=512)
        client.embed_video_segment(b"video")

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", "{}"))

        # Should specify dimension
        assert body.get("embeddingConfig", {}).get("outputEmbeddingLength") == 512


class TestErrorHandling:
    """Tests for error scenarios."""

    @patch("boto3.client")
    def test_handles_api_error(self, mock_boto3_client):
        """Test error handling for API failures."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid input"}}, "InvokeModel"
        )
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()

        with pytest.raises(ClientError):
            client.embed_video_segment(b"invalid content")

    @patch("boto3.client")
    def test_handles_empty_response(self, mock_boto3_client):
        """Test handling of empty embedding response."""
        mock_client = MagicMock()
        mock_response = {}  # Empty response
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=lambda: json.dumps(mock_response).encode())
        }
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient()

        from ragstack_common.exceptions import MediaProcessingError

        with pytest.raises((MediaProcessingError, KeyError, ValueError)):
            client.embed_video_segment(b"content")


class TestRetryLogic:
    """Tests for retry behavior."""

    @patch("time.sleep")
    @patch("boto3.client")
    def test_retries_on_throttling(self, mock_boto3_client, mock_sleep):
        """Test that throttling errors are retried."""
        mock_client = MagicMock()
        mock_response = {"embedding": [0.1] * 1024}

        # First call throttles, second succeeds
        mock_client.invoke_model.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                "InvokeModel",
            ),
            {"body": MagicMock(read=lambda: json.dumps(mock_response).encode())},
        ]
        mock_boto3_client.return_value = mock_client

        client = NovaEmbeddingsClient(max_retries=2)
        result = client.embed_video_segment(b"video")

        assert "embedding" in result
        assert mock_client.invoke_model.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
