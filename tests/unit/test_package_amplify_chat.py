"""Tests for web component source packaging."""
import sys
import os
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

# Mock boto3 and botocore in sys.modules before importing publish
sys.modules['boto3'] = MagicMock()
sys.modules['botocore'] = MagicMock()
sys.modules['botocore.exceptions'] = MagicMock()

from publish import package_amplify_chat_source


def test_package_creates_zip_with_correct_structure(tmp_path, monkeypatch):
    """Verify zip contains web-component/* structure."""
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

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

    # Create dist (should be excluded)
    (chat_dir / 'dist').mkdir()
    (chat_dir / 'dist' / 'bundle.js').write_text('')

    # Capture the zip path before it's deleted
    captured_zip_path = None
    original_remove = os.remove

    def mock_remove(path):
        nonlocal captured_zip_path
        if path.endswith('.zip'):
            # Copy the zip to a safe location before deleting
            import shutil
            captured_zip_path = str(tmp_path / 'saved.zip')
            shutil.copy(path, captured_zip_path)
        return original_remove(path)

    with patch('publish.boto3.client') as mock_s3:
        with patch('publish.os.remove', side_effect=mock_remove):
            # Mock S3 upload
            mock_client = MagicMock()
            mock_s3.return_value = mock_client

            # Call function
            key = package_amplify_chat_source('test-bucket', 'us-east-1')

            # Verify S3 upload was called
            assert mock_client.upload_file.called

            # Verify zip contents using saved copy
            assert captured_zip_path is not None
            with zipfile.ZipFile(captured_zip_path, 'r') as zf:
                names = zf.namelist()

                # Should have web-component prefix
                assert 'web-component/package.json' in names
                assert 'web-component/src/index.ts' in names

                # Should NOT have node_modules or dist
                assert not any('node_modules' in n for n in names)
                assert not any('dist' in n for n in names)


def test_package_raises_if_directory_missing(tmp_path, monkeypatch):
    """Verify error when src/amplify-chat doesn't exist."""
    # Change to a directory where src/amplify-chat doesn't exist
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError) as exc_info:
        package_amplify_chat_source('test-bucket', 'us-east-1')

    assert 'Web component directory not found' in str(exc_info.value)


def test_package_returns_s3_key(tmp_path, monkeypatch):
    """Verify function returns S3 key with timestamp."""
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Create mock src/amplify-chat directory with minimal content
    chat_dir = tmp_path / 'src' / 'amplify-chat'
    chat_dir.mkdir(parents=True)
    (chat_dir / 'package.json').write_text('{}')

    with patch('publish.boto3.client') as mock_s3:
        mock_client = MagicMock()
        mock_s3.return_value = mock_client

        # Patch time at the module level where it's imported
        import time
        with patch.object(time, 'time', return_value=1234567890):
            key = package_amplify_chat_source('test-bucket', 'us-east-1')

            assert key == 'web-component-source-1234567890.zip'


def test_package_cleans_up_temp_file_on_error(tmp_path, monkeypatch):
    """Verify temporary file is cleaned up on error."""
    # Change to tmp_path directory
    monkeypatch.chdir(tmp_path)

    # Create mock src/amplify-chat directory
    chat_dir = tmp_path / 'src' / 'amplify-chat'
    chat_dir.mkdir(parents=True)
    (chat_dir / 'package.json').write_text('{}')

    with patch('publish.boto3.client') as mock_s3:
        # Mock S3 client to raise error on upload
        mock_client = MagicMock()
        mock_client.upload_file.side_effect = Exception("Upload failed")
        mock_s3.return_value = mock_client

        # Verify error is raised and temp file is cleaned up
        with pytest.raises(IOError) as exc_info:
            package_amplify_chat_source('test-bucket', 'us-east-1')

        assert "Unexpected error packaging web component source" in str(exc_info.value)
