"""Unit tests for publish.py argument parsing"""

import argparse

import pytest


def test_project_name_required():
    """Test that --project-name is required"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--region", required=True)

    with pytest.raises(SystemExit):
        parser.parse_args(["--admin-email", "test@example.com", "--region", "us-east-1"])


def test_admin_email_required():
    """Test that --admin-email is required"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--region", required=True)

    with pytest.raises(SystemExit):
        parser.parse_args(["--project-name", "test", "--region", "us-east-1"])


def test_region_required():
    """Test that --region is required"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--region", required=True)

    with pytest.raises(SystemExit):
        parser.parse_args(["--project-name", "test", "--admin-email", "test@example.com"])


def test_skip_ui_optional():
    """Test that --skip-ui is optional"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--skip-ui", action="store_true")

    # Without --skip-ui
    args = parser.parse_args(
        ["--project-name", "test", "--admin-email", "test@example.com", "--region", "us-east-1"]
    )
    assert args.skip_ui is False

    # With --skip-ui
    args = parser.parse_args(
        [
            "--project-name",
            "test",
            "--admin-email",
            "test@example.com",
            "--region",
            "us-east-1",
            "--skip-ui",
        ]
    )
    assert args.skip_ui is True


def test_all_required_args_provided():
    """Test successful parsing with all required args"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--skip-ui", action="store_true")

    args = parser.parse_args(
        [
            "--project-name",
            "customer-docs",
            "--admin-email",
            "admin@example.com",
            "--region",
            "us-east-1",
        ]
    )

    assert args.project_name == "customer-docs"
    assert args.admin_email == "admin@example.com"
    assert args.region == "us-east-1"
    assert args.skip_ui is False
