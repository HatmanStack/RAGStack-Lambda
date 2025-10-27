"""Unit tests for validation functions in publish.py"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import publish


class TestValidateProjectName:
    """Tests for validate_project_name()"""

    def test_valid_project_names(self):
        """Test valid project names pass validation"""
        valid_names = [
            'ab',  # minimum length
            'customer-docs',
            'legal-archive',
            'hr-records',
            'project-x',
            'test123',
            'abc-123-xyz',
            'a' * 32,  # maximum length
        ]

        for name in valid_names:
            assert publish.validate_project_name(name) is True, f"Should accept: {name}"

    def test_empty_project_name(self):
        """Test empty project name raises error"""
        with pytest.raises(ValueError, match="cannot be empty"):
            publish.validate_project_name('')

    def test_too_short(self):
        """Test project name shorter than 2 chars raises error"""
        with pytest.raises(ValueError, match="at least 2 characters"):
            publish.validate_project_name('a')

    def test_too_long(self):
        """Test project name longer than 32 chars raises error"""
        with pytest.raises(ValueError, match="at most 32 characters"):
            publish.validate_project_name('a' * 33)

    def test_must_start_with_letter(self):
        """Test project name must start with letter"""
        invalid = ['1project', '-project', '9abc']
        for name in invalid:
            with pytest.raises(ValueError, match="must start with a letter"):
                publish.validate_project_name(name)

    def test_must_start_with_lowercase(self):
        """Test project name must start with lowercase letter"""
        with pytest.raises(ValueError, match="must start with a lowercase letter"):
            publish.validate_project_name('Project')

    def test_invalid_characters(self):
        """Test project names with invalid characters raise error"""
        invalid = [
            'project_name',  # underscore
            'project name',  # space
            'project.name',  # dot
            'project@name',  # special char
            'Project-Name',  # uppercase
        ]

        for name in invalid:
            with pytest.raises(ValueError, match="invalid character|lowercase"):
                publish.validate_project_name(name)


class TestValidateRegion:
    """Tests for validate_region()"""

    def test_valid_regions(self):
        """Test valid AWS regions pass validation"""
        valid_regions = [
            'us-east-1',
            'us-west-2',
            'eu-west-1',
            'ap-southeast-1',
        ]

        for region in valid_regions:
            assert publish.validate_region(region) is True, f"Should accept: {region}"

    def test_empty_region(self):
        """Test empty region raises error"""
        with pytest.raises(ValueError, match="cannot be empty"):
            publish.validate_region('')

    def test_invalid_region(self):
        """Test invalid region raises error"""
        with pytest.raises(ValueError, match="Invalid AWS region"):
            publish.validate_region('invalid-region-1')

    def test_nonexistent_region(self, capsys):
        """Test non-existent AWS region logs warning but passes"""
        assert publish.validate_region('us-central-1') is True
        captured = capsys.readouterr()
        assert "not in known list" in captured.out


class TestValidateEmail:
    """Tests for validate_email()"""

    def test_valid_emails(self):
        """Test valid email addresses"""
        valid_emails = [
            'admin@example.com',
            'user.name@example.com',
            'user+tag@example.co.uk',
            'test@subdomain.example.com',
        ]

        for email in valid_emails:
            assert publish.validate_email(email) is True, f"Should accept: {email}"

    def test_invalid_emails(self):
        """Test invalid email addresses"""
        invalid_emails = [
            '',
            'notanemail',
            '@example.com',
            'user@',
            'user@.com',
            'user @example.com',  # space
        ]

        for email in invalid_emails:
            assert publish.validate_email(email) is False, f"Should reject: {email}"
