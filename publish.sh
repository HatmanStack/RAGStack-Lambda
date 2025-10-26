#!/bin/bash

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

##############################################################################################
# RAGStack-Lambda Publisher Wrapper Script
#
# This script acts as a wrapper for publish.py, ensuring that:
# 1. Python 3.12+ is available
# 2. Required Python packages are installed
# 3. Proper arguments are passed to the Python script
##############################################################################################

set -e # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
  echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
  echo -e "${RED}❌ $1${NC}"
}

# Print usage information
print_usage() {
  echo "Usage: $0 [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  --admin-email EMAIL    Admin user email address"
  echo "  --project-name NAME    Project name prefix (default: RAGStack)"
  echo "  --region REGION        AWS region (default: us-east-1)"
  echo "  --skip-ui              Skip UI build and deployment"
  echo "  --skip-build           Skip SAM build step"
  echo "  -h, --help             Show this help message"
  echo ""
  echo "Examples:"
  echo "  $0"
  echo "  $0 --admin-email admin@example.com --project-name MyRAGStack"
  echo "  $0 --region us-west-2"
}

# Check if Python 3.12+ is available
check_python_version() {
  print_info "Checking Python version..."

  # Try python3 first, then python
  for python_cmd in python3 python; do
    if command -v "$python_cmd" >/dev/null 2>&1; then
      version=$($python_cmd --version 2>&1 | cut -d' ' -f2)
      major=$(echo "$version" | cut -d'.' -f1)
      minor=$(echo "$version" | cut -d'.' -f2)

      if [[ "$major" -eq 3 && "$minor" -ge 12 ]]; then
        PYTHON_CMD="$python_cmd"
        print_success "Found Python $version at $(which $python_cmd)"
        return 0
      elif [[ "$major" -eq 3 ]]; then
        print_warning "Found Python $version, but Python 3.12+ is required"
      fi
    fi
  done

  print_error "Python 3.12+ is required but not found"
  print_info "Please install Python 3.12 or later and try again"
  exit 1
}

# Check if Node.js and npm are available for UI build
check_nodejs_dependencies() {
  if [[ "$*" == *"--skip-ui"* ]]; then
    print_info "Skipping Node.js check (--skip-ui flag detected)"
    return 0
  fi

  print_info "Checking Node.js dependencies for UI build..."

  # Check Node.js
  if ! command -v node >/dev/null 2>&1; then
    print_error "Node.js not found but is required for UI build"
    print_info "Install Node.js 18+ from: https://nodejs.org/"
    print_info "Or use --skip-ui flag to skip UI build"
    exit 1
  fi

  # Check npm
  if ! command -v npm >/dev/null 2>&1; then
    print_error "npm not found but is required for UI build"
    print_info "npm is typically installed with Node.js"
    exit 1
  fi

  # Check Node.js version (require 18+)
  node_version=$(node --version 2>/dev/null | sed 's/v//')
  node_major=$(echo "$node_version" | cut -d'.' -f1)

  if [[ "$node_major" -lt 18 ]]; then
    print_error "Node.js $node_version found, but 18+ is required for UI build"
    print_info "Please upgrade Node.js to version 18 or later"
    print_info "Or use --skip-ui flag to skip UI build"
    exit 1
  else
    print_success "Found Node.js $node_version and npm $(npm --version)"
  fi
}

# Check if required packages are installed and install them if missing
check_and_install_packages() {
  print_info "Checking required Python packages..."

  # List of required packages (import_name:package_name pairs)
  required_packages=(
    "boto3:boto3"
  )
  missing_packages=()

  # Check each package
  for package_pair in "${required_packages[@]}"; do
    import_name="${package_pair%%:*}"
    package_name="${package_pair##*:}"
    if ! $PYTHON_CMD -c "import $import_name" >/dev/null 2>&1; then
      missing_packages+=("$package_name")
    fi
  done

  # Install missing packages if any
  if [[ ${#missing_packages[@]} -gt 0 ]]; then
    print_warning "Missing packages: ${missing_packages[*]}"
    print_info "Installing missing packages..."

    for package in "${missing_packages[@]}"; do
      print_info "Installing $package..."
      if $PYTHON_CMD -m pip install "$package" --quiet; then
        print_success "Installed $package"
      else
        print_error "Failed to install $package"
        print_info "Please install manually: $PYTHON_CMD -m pip install $package"
        exit 1
      fi
    done
  else
    print_success "All required packages are installed"
  fi
}

# Check if AWS CLI is configured
check_aws_cli() {
  print_info "Checking AWS CLI configuration..."

  if ! command -v aws >/dev/null 2>&1; then
    print_error "AWS CLI not found"
    print_info "Install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
  fi

  # Check if credentials are configured
  if ! aws sts get-caller-identity >/dev/null 2>&1; then
    print_error "AWS credentials not configured"
    print_info "Run: aws configure"
    exit 1
  fi

  print_success "AWS CLI configured"
}

# Check if SAM CLI is installed
check_sam_cli() {
  print_info "Checking SAM CLI..."

  if ! command -v sam >/dev/null 2>&1; then
    print_error "SAM CLI not found"
    print_info "Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html"
    exit 1
  fi

  sam_version=$(sam --version | awk '{print $4}')
  print_success "Found SAM CLI $sam_version"
}

# Main execution
main() {
  print_info "RAGStack-Lambda Publisher"
  print_info "=========================="

  # Check Python version
  check_python_version

  # Check Node.js dependencies (skip if --skip-ui is set)
  check_nodejs_dependencies "$@"

  # Check and install required packages
  check_and_install_packages

  # Check AWS CLI
  check_aws_cli

  # Check SAM CLI
  check_sam_cli

  # Check if publish.py exists
  if [[ ! -f "publish.py" ]]; then
    print_error "publish.py not found in current directory"
    print_info "Please run this script from the RAGStack-Lambda root directory"
    exit 1
  fi

  # Execute publish.py with all arguments
  print_info "Launching publish.py..."
  exec $PYTHON_CMD publish.py "$@"
}

# Handle help flag
if [[ "$1" == "-h" || "$1" == "--help" ]]; then
  print_usage
  exit 0
fi

# Run main function with all arguments
main "$@"
