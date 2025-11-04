#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
RAGStack-Lambda Test Runner

Runs all tests (Node and Python) with fresh npm dependencies.

Usage:
    python test.py
"""

import subprocess
import sys


class Colors:
    """ANSI color codes for terminal output."""
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'


def log_info(msg):
    print(f"{Colors.OKBLUE}ℹ {msg}{Colors.ENDC}")


def log_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def log_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def run_command(cmd, cwd=None):
    """Run shell command."""
    log_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, cwd=cwd)
    return result.returncode == 0


def check_python_version():
    """Check if Python 3.12+ is available."""
    version_info = sys.version_info

    if version_info[0] < 3 or (version_info[0] == 3 and version_info[1] < 12):
        log_error("Python 3.12+ is required")
        log_info(f"Current version: Python {version_info[0]}.{version_info[1]}.{version_info[2]}")
        sys.exit(1)

    log_success(f"Found Python {version_info[0]}.{version_info[1]}.{version_info[2]}")
    return True


def check_node():
    """Check if Node.js and npm are available."""
    log_info("Checking Node.js...")

    node_result = subprocess.run(['node', '--version'],
                                capture_output=True,
                                text=True)

    if node_result.returncode != 0:
        log_error("Node.js not found")
        log_info("Install from: https://nodejs.org/")
        sys.exit(1)

    npm_result = subprocess.run(['npm', '--version'],
                               capture_output=True,
                               text=True)

    if npm_result.returncode != 0:
        log_error("npm not found")
        sys.exit(1)

    log_success(f"Found Node {node_result.stdout.strip()} and npm {npm_result.stdout.strip()}")
    return True


def main():
    """Main test runner."""
    print(f"\n{'=' * 60}")
    print("RAGStack-Lambda Test Runner")
    print(f"{'=' * 60}\n")

    try:
        # Check prerequisites
        log_info("Checking prerequisites...")
        check_python_version()
        check_node()
        log_success("All prerequisites met\n")

        # Install Node dependencies (root)
        log_info("Installing root Node dependencies...")
        if not run_command(['npm', 'install']):
            log_error("npm install failed at root")
            sys.exit(1)
        log_success("Root dependencies installed")

        # Install UI dependencies (src/ui)
        log_info("Installing UI Node dependencies...")
        if not run_command(['npm', 'install'], cwd='src/ui'):
            log_error("npm install failed in src/ui")
            sys.exit(1)
        log_success("UI dependencies installed\n")

        # Run all tests (lint + test)
        log_info("Running tests and linting...")
        if not run_command(['npm', 'run', 'test:all']):
            log_error("Tests failed")
            sys.exit(1)

        print(f"\n{'=' * 60}")
        log_success("All tests passed!")
        print(f"{'=' * 60}\n")

    except Exception as e:
        log_error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
