"""Unit tests for prerequisite check functions in publish.py"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import publish


class TestCheckPythonVersion:
    """Tests for check_python_version()"""

    def test_python_312_passes(self):
        """Test Python 3.12+ passes"""
        with patch("sys.version_info", (3, 12, 0)):
            assert publish.check_python_version() is True

    def test_python_313_passes(self):
        """Test Python 3.13+ passes"""
        with patch("sys.version_info", (3, 13, 0)):
            assert publish.check_python_version() is True

    def test_python_311_fails(self):
        """Test Python 3.11 fails"""
        with patch("sys.version_info", (3, 11, 0)), pytest.raises(SystemExit):
            publish.check_python_version()

    def test_python_2_fails(self):
        """Test Python 2.x fails"""
        with patch("sys.version_info", (2, 7, 18)), pytest.raises(SystemExit):
            publish.check_python_version()


class TestCheckNodejsVersion:
    """Tests for check_nodejs_version()"""

    def test_skip_ui_bypasses_check(self):
        """Test --skip-ui flag bypasses Node.js check"""
        assert publish.check_nodejs_version(skip_ui=True) is True

    @patch("subprocess.run")
    def test_nodejs_18_passes(self, mock_run):
        """Test Node.js 18+ passes"""
        # Mock node --version
        node_result = MagicMock()
        node_result.returncode = 0
        node_result.stdout = "v18.0.0\n"

        # Mock npm --version
        npm_result = MagicMock()
        npm_result.returncode = 0
        npm_result.stdout = "9.0.0\n"

        mock_run.side_effect = [node_result, npm_result]

        assert publish.check_nodejs_version(skip_ui=False) is True

    @patch("subprocess.run")
    def test_nodejs_17_fails(self, mock_run):
        """Test Node.js 17 fails"""
        node_result = MagicMock()
        node_result.returncode = 0
        node_result.stdout = "v17.9.0\n"

        npm_result = MagicMock()
        npm_result.returncode = 0
        npm_result.stdout = "8.0.0\n"

        mock_run.side_effect = [node_result, npm_result]

        with pytest.raises(SystemExit):
            publish.check_nodejs_version(skip_ui=False)

    @patch("subprocess.run")
    def test_nodejs_not_found_fails(self, mock_run):
        """Test missing Node.js fails"""
        node_result = MagicMock()
        node_result.returncode = 1

        mock_run.return_value = node_result

        with pytest.raises(SystemExit):
            publish.check_nodejs_version(skip_ui=False)


class TestCheckAwsCli:
    """Tests for check_aws_cli()"""

    @patch("subprocess.run")
    def test_aws_cli_configured_passes(self, mock_run):
        """Test configured AWS CLI passes"""
        # Mock aws --version
        version_result = MagicMock()
        version_result.returncode = 0

        # Mock aws sts get-caller-identity
        creds_result = MagicMock()
        creds_result.returncode = 0

        mock_run.side_effect = [version_result, creds_result]

        assert publish.check_aws_cli() is True

    @patch("subprocess.run")
    def test_aws_cli_not_found_fails(self, mock_run):
        """Test missing AWS CLI fails"""
        result = MagicMock()
        result.returncode = 1

        mock_run.return_value = result

        with pytest.raises(SystemExit):
            publish.check_aws_cli()

    @patch("subprocess.run")
    def test_aws_cli_not_configured_fails(self, mock_run):
        """Test AWS CLI without credentials fails"""
        # Version check passes
        version_result = MagicMock()
        version_result.returncode = 0

        # Credentials check fails
        creds_result = MagicMock()
        creds_result.returncode = 1

        mock_run.side_effect = [version_result, creds_result]

        with pytest.raises(SystemExit):
            publish.check_aws_cli()


class TestCheckSamCli:
    """Tests for check_sam_cli()"""

    @patch("subprocess.run")
    def test_sam_cli_found_passes(self, mock_run):
        """Test installed SAM CLI passes"""
        result = MagicMock()
        result.returncode = 0
        result.stdout = "SAM CLI, version 1.100.0\n"

        mock_run.return_value = result

        assert publish.check_sam_cli() is True

    @patch("subprocess.run")
    def test_sam_cli_not_found_fails(self, mock_run):
        """Test missing SAM CLI fails"""
        result = MagicMock()
        result.returncode = 1

        mock_run.return_value = result

        with pytest.raises(SystemExit):
            publish.check_sam_cli()
