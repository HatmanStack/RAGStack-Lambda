#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
RAGStack-Lambda Deployment Script

Project-based deployment automation for RAGStack-Lambda stack.

Usage:
    python publish.py --project-name customer-docs --admin-email admin@example.com --region us-east-1
    python publish.py --project-name legal-archive --admin-email admin@example.com --region us-west-2 --skip-ui
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def log_info(msg):
    print(f"{Colors.OKBLUE}ℹ {msg}{Colors.ENDC}")


def log_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")


def log_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")


def log_warning(msg):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")


def run_command(cmd, check=True, capture_output=False, cwd=None):
    """Run shell command and return result."""
    log_info(f"Running: {' '.join(cmd)}")

    if capture_output:
        result = subprocess.run(cmd, capture_output=True, text=True, check=check, cwd=cwd)
        return result.stdout.strip()
    else:
        result = subprocess.run(cmd, check=check, cwd=cwd)
        return result.returncode == 0


def validate_email(email):
    """Validate email format."""
    pattern = r'^[\w.+-]+@([\w-]+\.)+[\w-]{2,6}$'
    return re.match(pattern, email) is not None


def validate_project_name(project_name):
    """
    Validate project name follows naming rules.

    Rules:
    - Lowercase alphanumeric and hyphens only
    - Must be 2-32 characters long
    - Must start with a letter

    Args:
        project_name: String to validate

    Returns:
        bool: True if valid

    Raises:
        ValueError: If project name is invalid with descriptive message
    """
    if not project_name:
        raise ValueError("Project name cannot be empty")

    if len(project_name) < 2:
        raise ValueError("Project name must be at least 2 characters long")

    if len(project_name) > 32:
        raise ValueError("Project name must be at most 32 characters long")

    if not project_name[0].isalpha():
        raise ValueError("Project name must start with a letter")

    if not project_name[0].islower():
        raise ValueError("Project name must start with a lowercase letter")

    # Check all characters are lowercase alphanumeric or hyphen
    for char in project_name:
        if not (char.islower() or char.isdigit() or char == '-'):
            raise ValueError(
                f"Project name contains invalid character '{char}'. "
                "Only lowercase letters, numbers, and hyphens are allowed"
            )

    return True


def validate_region(region):
    """
    Validate AWS region using regex pattern for future-proofing.

    AWS region format: 2-letter country code, direction, number
    Examples: us-east-1, eu-west-2, ap-southeast-3

    Args:
        region: AWS region string (e.g., 'us-east-1')

    Returns:
        bool: True if valid

    Raises:
        ValueError: If region format is invalid
    """
    if not region:
        raise ValueError("Region cannot be empty")

    # AWS region pattern: 2-letter country code, direction, number
    pattern = r'^[a-z]{2}-[a-z]+-\d+$'

    if not re.match(pattern, region):
        raise ValueError(
            f"Invalid AWS region format: {region}. "
            "Expected format like 'us-east-1', 'eu-west-2'"
        )

    # Optional: Check against known regions (as of 2025)
    # Log warning if region is not in known list (may be a new region)
    known_regions = [
        'us-east-1', 'us-east-2', 'us-west-1', 'us-west-2',
        'af-south-1',
        'ap-east-1', 'ap-south-1', 'ap-south-2',
        'ap-northeast-1', 'ap-northeast-2', 'ap-northeast-3',
        'ap-southeast-1', 'ap-southeast-2', 'ap-southeast-3', 'ap-southeast-4',
        'ca-central-1', 'ca-west-1',
        'eu-central-1', 'eu-central-2',
        'eu-west-1', 'eu-west-2', 'eu-west-3',
        'eu-south-1', 'eu-south-2',
        'eu-north-1',
        'il-central-1',
        'me-south-1', 'me-central-1',
        'sa-east-1',
    ]

    if region not in known_regions:
        log_warning(f"Region '{region}' not in known list (may be new region)")

    return True


def check_python_version():
    """
    Check if Python 3.12+ is available.

    Returns:
        bool: True if Python version is 3.12 or higher

    Raises:
        SystemExit: If Python version is insufficient
    """
    version_info = sys.version_info

    if version_info[0] < 3:
        log_error("Python 3.12+ is required")
        log_info("Current version: Python {}.{}.{}".format(
            version_info[0], version_info[1], version_info[2]
        ))
        sys.exit(1)

    if version_info[0] == 3 and version_info[1] < 12:
        log_error("Python 3.12+ is required")
        log_info("Current version: Python {}.{}.{}".format(
            version_info[0], version_info[1], version_info[2]
        ))
        log_info("Please upgrade Python and try again")
        sys.exit(1)

    log_success("Found Python {}.{}.{}".format(
        version_info[0], version_info[1], version_info[2]
    ))
    return True


def check_nodejs_version(skip_ui=False):
    """
    Check if Node.js 24+ and npm are available.

    Args:
        skip_ui: If True, skip Node.js check

    Returns:
        bool: True if Node.js and npm are available and version is sufficient

    Raises:
        SystemExit: If Node.js or npm not found or version insufficient
    """
    if skip_ui:
        log_info("Skipping Node.js check (--skip-ui flag detected)")
        return True

    log_info("Checking Node.js dependencies for UI build...")

    # Check Node.js exists
    node_result = subprocess.run(['node', '--version'],
                                capture_output=True,
                                text=True)

    if node_result.returncode != 0:
        log_error("Node.js not found but is required for UI build")
        log_info("Install Node.js 24+ from: https://nodejs.org/")
        log_info("Or use --skip-ui flag to skip UI build")
        sys.exit(1)

    # Check npm exists
    npm_result = subprocess.run(['npm', '--version'],
                               capture_output=True,
                               text=True)

    if npm_result.returncode != 0:
        log_error("npm not found but is required for UI build")
        log_info("npm is typically installed with Node.js")
        sys.exit(1)

    # Parse Node.js version
    node_version = node_result.stdout.strip().lstrip('v')
    npm_version = npm_result.stdout.strip()

    try:
        node_major = int(node_version.split('.')[0])

        if node_major < 24:
            log_error(f"Node.js {node_version} found, but 24+ is required for UI build")
            log_info("Please upgrade Node.js to version 24 or later")
            log_info("Or use --skip-ui flag to skip UI build")
            sys.exit(1)

        log_success(f"Found Node.js {node_version} and npm {npm_version}")
        return True

    except (ValueError, IndexError):
        log_error(f"Could not parse Node.js version: {node_version}")
        sys.exit(1)


def check_aws_cli():
    """
    Check if AWS CLI is installed and configured.

    Returns:
        bool: True if AWS CLI is configured with valid credentials

    Raises:
        SystemExit: If AWS CLI not found or not configured
    """
    log_info("Checking AWS CLI configuration...")

    # Check AWS CLI exists
    aws_result = subprocess.run(['aws', '--version'],
                               capture_output=True,
                               text=True)

    if aws_result.returncode != 0:
        log_error("AWS CLI not found")
        log_info("Install AWS CLI: https://aws.amazon.com/cli/")
        sys.exit(1)

    # Check credentials are configured
    creds_result = subprocess.run(['aws', 'sts', 'get-caller-identity'],
                                 capture_output=True,
                                 text=True)

    if creds_result.returncode != 0:
        log_error("AWS credentials not configured")
        log_info("Run: aws configure")
        sys.exit(1)

    log_success("AWS CLI configured")
    return True


def check_sam_cli():
    """
    Check if AWS SAM CLI is installed.

    Returns:
        bool: True if SAM CLI is installed

    Raises:
        SystemExit: If SAM CLI not found
    """
    log_info("Checking SAM CLI...")

    sam_result = subprocess.run(['sam', '--version'],
                               capture_output=True,
                               text=True)

    if sam_result.returncode != 0:
        log_error("SAM CLI not found")
        log_info("Install SAM CLI: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html")
        sys.exit(1)

    # Parse version from output (format: "SAM CLI, version X.Y.Z")
    version_output = sam_result.stdout.strip()
    log_success(f"Found {version_output}")
    return True


def sam_build():
    """Build SAM application."""
    log_info("Building SAM application...")
    run_command(["sam", "build", "--parallel", "--cached"])
    log_success("SAM build complete")


def handle_failed_stack(stack_name, region):
    """
    Check if stack exists and is in a failed state (ROLLBACK_COMPLETE or CREATE_FAILED).

    If the stack is in a failed state, delete it so a fresh deployment can proceed.
    This handles the case where a previous deployment failed and needs to be retried.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region

    Returns:
        bool: True if stack was deleted or doesn't exist, False if stack exists and is healthy

    Raises:
        IOError: If deletion fails
    """
    cf_client = boto3.client('cloudformation', region_name=region)

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        stack_status = stack['StackStatus']

        # Check if stack is already being deleted
        if stack_status == 'DELETE_IN_PROGRESS':
            log_info(f"Stack '{stack_name}' is already being deleted, waiting for completion...")
            try:
                waiter = cf_client.get_waiter('stack_delete_complete')
                log_info("Waiting for stack deletion to complete (this may take several minutes)...")
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={
                        'Delay': 30,  # Check every 30 seconds
                        'MaxAttempts': 20  # Wait up to 10 minutes (20 * 30s)
                    }
                )
                log_success(f"Stack '{stack_name}' deleted successfully")
                return True
            except Exception as e:
                log_error(f"Stack deletion timed out or failed: {e}")
                log_error(f"Stack '{stack_name}' is still deleting. Please wait for deletion to complete:")
                log_error(f"  1. Check CloudFormation console: https://console.aws.amazon.com/cloudformation")
                log_error(f"  2. Or run: aws cloudformation wait stack-delete-complete --stack-name {stack_name}")
                log_error(f"  3. Then retry this deployment")
                raise IOError(f"Stack deletion timeout - stack '{stack_name}' may still be deleting") from e

        # Check if stack is in a failed/rollback state
        if stack_status in ['ROLLBACK_COMPLETE', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_ROLLBACK_COMPLETE', 'ROLLBACK_FAILED']:
            log_warning(f"Stack '{stack_name}' is in {stack_status} state")
            log_info(f"Deleting failed stack '{stack_name}'...")

            try:
                cf_client.delete_stack(StackName=stack_name)

                # Wait for deletion to complete
                waiter = cf_client.get_waiter('stack_delete_complete')
                log_info("Waiting for stack deletion to complete (this may take several minutes)...")
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={
                        'Delay': 30,  # Check every 30 seconds
                        'MaxAttempts': 20  # Wait up to 10 minutes (20 * 30s)
                    }
                )

                log_success(f"Stack '{stack_name}' deleted successfully")
                return True
            except Exception as e:
                log_error(f"Stack deletion timed out: {e}")
                log_error(f"Stack '{stack_name}' deletion is taking longer than expected. Please verify deletion:")
                log_error(f"  1. Check CloudFormation console: https://console.aws.amazon.com/cloudformation")
                log_error(f"  2. Or run: aws cloudformation describe-stacks --stack-name {stack_name}")
                log_error(f"  3. If stuck, manually delete: aws cloudformation delete-stack --stack-name {stack_name}")
                log_error(f"  4. Then retry this deployment")
                raise IOError(f"Stack deletion timeout - cannot proceed while stack '{stack_name}' may still be deleting") from e

        # Stack exists and is in a healthy state
        return False

    except cf_client.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']

        # Stack doesn't exist - this is fine, we can proceed
        if error_code == 'ValidationError' and 'does not exist' in str(e):
            log_info(f"Stack '{stack_name}' does not exist, proceeding with fresh deployment")
            return True

        # Other errors should be raised
        raise IOError(f"Failed to check stack status: {e}") from e


def create_sam_artifact_bucket(project_name, region):
    """
    Create S3 bucket for deployment artifacts if it doesn't exist.

    This single bucket stores both SAM/CloudFormation artifacts and UI source code.
    SAM uses it for Lambda functions, layers, and templates.
    CodeBuild uses it to fetch UI source for building and deploying.

    Args:
        project_name: Project name for bucket naming
        region: AWS region

    Returns:
        str: Bucket name

    Raises:
        IOError: If bucket creation fails
    """
    s3_client = boto3.client('s3', region_name=region)
    sts_client = boto3.client('sts', region_name=region)

    # Get account ID for bucket naming
    try:
        account_id = sts_client.get_caller_identity()['Account']
    except ClientError as e:
        raise IOError(f"Failed to get AWS account ID: {e}") from e

    # Use project-specific bucket for all deployment artifacts
    bucket_name = f'ragstack-{project_name}-artifacts-{account_id}'

    # Create bucket if it doesn't exist
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        log_info(f"Using existing artifact bucket: {bucket_name}")
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')

        if error_code == '404' or error_code == 'NoSuchBucket':
            log_info(f"Creating artifact bucket: {bucket_name}")
            try:
                if region == 'us-east-1':
                    s3_client.create_bucket(Bucket=bucket_name)
                else:
                    s3_client.create_bucket(
                        Bucket=bucket_name,
                        CreateBucketConfiguration={'LocationConstraint': region}
                    )

                # Enable versioning for artifact tracking
                s3_client.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={'Status': 'Enabled'}
                )

                log_success(f"Created artifact bucket: {bucket_name}")
            except ClientError as create_error:
                raise IOError(f"Failed to create S3 bucket {bucket_name}: {create_error}") from create_error
        else:
            raise IOError(f"Failed to access S3 bucket {bucket_name}: {e}") from e

    return bucket_name


def sam_deploy(project_name, admin_email, region, artifact_bucket, ui_source_key=None, skip_ui=False):
    """
    Deploy SAM application with project-based naming.

    Args:
        project_name: Project name for resource naming
        admin_email: Admin email for Cognito and alerts
        region: AWS region
        artifact_bucket: S3 bucket for SAM artifacts and UI source
        ui_source_key: S3 key for UI source zip (if not skip_ui)
        skip_ui: Whether to skip UI deployment

    Returns:
        str: CloudFormation stack name
    """
    log_info(f"Deploying project '{project_name}' to {region}...")

    # Stack name follows pattern: RAGStack-{project-name}
    stack_name = f"RAGStack-{project_name}"

    # Check if stack exists and get existing DeploymentSuffix
    cf_client = boto3.client('cloudformation', region_name=region)
    deployment_suffix = None

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        # Stack exists - retrieve existing DeploymentSuffix parameter
        parameters = response['Stacks'][0].get('Parameters', [])
        for param in parameters:
            if param['ParameterKey'] == 'DeploymentSuffix':
                deployment_suffix = param['ParameterValue']
                log_info(f"Reusing existing deployment suffix: {deployment_suffix}")
                break
    except cf_client.exceptions.ClientError as e:
        if 'does not exist' in str(e):
            log_info("Stack does not exist - will create new stack")
        else:
            raise

    # Generate new suffix only if stack doesn't exist or suffix not found
    if not deployment_suffix:
        import random
        import string
        deployment_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        log_info(f"Generated new deployment suffix: {deployment_suffix}")

    # Base parameter overrides
    param_overrides = [
        f"DeploymentSuffix={deployment_suffix}",
        f"ProjectName={project_name}",
        f"AdminEmail={admin_email}",
        "BedrockOcrModelId=meta.llama3-2-90b-instruct-v1:0",
    ]

    # Add UI parameters if building UI
    if not skip_ui and ui_source_key:
        log_info("UI will be deployed via CodeBuild during stack creation")
        param_overrides.append(f"UISourceBucket={artifact_bucket}")
        param_overrides.append(f"UISourceKey={ui_source_key}")

    cmd = [
        "sam", "deploy",
        "--stack-name", stack_name,
        "--region", region,
        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND",
        "--s3-bucket", artifact_bucket,
        "--no-confirm-changeset",
        "--parameter-overrides",
    ] + param_overrides

    run_command(cmd)

    # Enable termination protection on the stack to prevent accidental deletion
    try:
        log_info("Enabling stack termination protection...")
        cf_client.update_termination_protection(
            StackName=stack_name,
            EnableTerminationProtection=True
        )
        log_success("Stack termination protection enabled")
    except Exception as e:
        log_error(f"Warning: Failed to enable termination protection: {e}")

    log_success(f"Deployment of project '{project_name}' complete")
    return stack_name


def package_ui_source(bucket_name, region):
    """
    Package UI source code as zip and upload to S3.

    Creates a zip file of the UI source (excluding node_modules and build directories),
    uploads it to the provided S3 bucket, and returns the bucket/key for CloudFormation.

    Args:
        bucket_name: S3 bucket name to upload to
        region: AWS region for bucket operations

    Returns:
        str: S3 key of uploaded UI source zip

    Raises:
        FileNotFoundError: If UI source directory doesn't exist
        IOError: If packaging or upload fails
    """
    import zipfile
    import tempfile
    import time
    from pathlib import Path

    log_info("Packaging UI source code...")

    ui_dir = Path('src/ui')
    if not ui_dir.exists():
        raise FileNotFoundError(f"UI directory not found: {ui_dir}")

    # Create temporary zip file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        zip_path = tmp_file.name

    try:
        # Create zip file, excluding node_modules and build
        log_info("Creating UI source zip file...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in ui_dir.rglob('*'):
                if file_path.is_file():
                    # Skip node_modules and build directories
                    if 'node_modules' in file_path.parts or 'build' in file_path.parts:
                        continue

                    # Store relative to src/ (include 'ui' folder in zip)
                    arcname = file_path.relative_to(ui_dir.parent)
                    zipf.write(file_path, arcname)

        log_success(f"UI source packaged: {zip_path}")

        # Upload to S3
        s3_client = boto3.client('s3', region_name=region)

        # Upload with timestamp-based key
        timestamp = int(time.time())
        key = f'ui-source-{timestamp}.zip'

        log_info(f"Uploading to s3://{bucket_name}/{key}...")
        try:
            s3_client.upload_file(zip_path, bucket_name, key)
            log_success("UI source uploaded to S3")
        except ClientError as e:
            raise IOError(f"Failed to upload UI source to S3: {e}") from e

        # Clean up temporary file
        os.remove(zip_path)

        return key

    except (FileNotFoundError, IOError):
        # Re-raise expected exceptions
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise
    except Exception as e:
        # Clean up temporary file on unexpected error
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise IOError(f"Unexpected error packaging UI source: {e}") from e


def package_amplify_chat_source(bucket_name, region):
    """
    Package web component source code as zip and upload to S3.

    Creates a zip file of src/amplify-chat/ (excluding node_modules and dist),
    uploads it to the provided S3 bucket, and returns the S3 key for CodeBuild.

    Args:
        bucket_name: S3 bucket name to upload to
        region: AWS region for bucket operations

    Returns:
        str: S3 key of uploaded web component source zip

    Raises:
        FileNotFoundError: If src/amplify-chat/ doesn't exist
        IOError: If packaging or upload fails
    """
    import zipfile
    import tempfile
    import time
    from pathlib import Path

    log_info("Packaging web component source...")

    chat_dir = Path('src/amplify-chat')
    if not chat_dir.exists():
        raise FileNotFoundError(f"Web component directory not found: {chat_dir}")

    # Create temporary zip file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        zip_path = tmp_file.name

    try:
        # Create zip file, excluding node_modules and dist
        log_info("Creating web component source zip file...")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in chat_dir.rglob('*'):
                if file_path.is_file():
                    # Skip node_modules and dist directories
                    if 'node_modules' in file_path.parts or 'dist' in file_path.parts:
                        continue

                    # Store as web-component/* (CodeBuild expects this structure)
                    arcname = Path('web-component') / file_path.relative_to(chat_dir)
                    zipf.write(file_path, arcname)

        log_success(f"Web component source packaged: {zip_path}")

        # Upload to S3
        s3_client = boto3.client('s3', region_name=region)

        # Upload with timestamp-based key
        timestamp = int(time.time())
        key = f'web-component-source-{timestamp}.zip'

        log_info(f"Uploading to s3://{bucket_name}/{key}...")
        try:
            s3_client.upload_file(zip_path, bucket_name, key)
            log_success("Web component source uploaded to S3")
        except ClientError as e:
            raise IOError(f"Failed to upload web component source to S3: {e}") from e

        # Clean up temporary file
        os.remove(zip_path)

        return key

    except (FileNotFoundError, IOError):
        # Re-raise expected exceptions
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise
    except Exception as e:
        # Clean up temporary file on unexpected error
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise IOError(f"Unexpected error packaging web component source: {e}") from e


def get_stack_outputs(stack_name, region="us-east-1"):
    """Get CloudFormation stack outputs."""
    log_info(f"Fetching stack outputs for {stack_name}...")

    cf_client = boto3.client('cloudformation', region_name=region)

    try:
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])

        output_dict = {}
        for item in outputs:
            output_dict[item['OutputKey']] = item['OutputValue']

        return output_dict
    except Exception as e:
        log_error(f"Failed to get stack outputs: {e}")
        return {}


def get_amplify_stack_outputs(project_name, region):
    """
    Get CloudFormation stack outputs from Amplify deployment.

    Amplify Gen 2 creates stacks with pattern: amplify-{appId}-{branch}-{hash}
    We search for stacks starting with "amplify-" to find the deployed stack.

    Args:
        project_name: Project name (used for identification)
        region: AWS region

    Returns:
        dict: Stack outputs as key-value pairs
            {
                'WebComponentCDN': 'https://d123.cloudfront.net/amplify-chat.js',
                'AssetBucketName': 'amplify-stack-assets-xyz',
                'BuildProjectName': 'amplify-stack-build',
                'DistributionId': 'E1234567890ABC'
            }

    Raises:
        ValueError: If Amplify stack not found or has no outputs
    """
    log_info("Fetching Amplify stack outputs...")

    cf_client = boto3.client('cloudformation', region_name=region)

    try:
        # List all stacks (active only)
        paginator = cf_client.get_paginator('list_stacks')
        stack_iterator = paginator.paginate(
            StackStatusFilter=[
                'CREATE_COMPLETE',
                'UPDATE_COMPLETE',
                'UPDATE_ROLLBACK_COMPLETE'
            ]
        )

        # Find Amplify stacks with timestamps (collect from list_stacks)
        amplify_stacks = []
        for page in stack_iterator:
            for stack in page['StackSummaries']:
                if stack['StackName'].startswith('amplify-'):
                    amplify_stacks.append({
                        'StackName': stack['StackName'],
                        'LastUpdatedTime': stack.get('LastUpdatedTime', stack['CreationTime'])
                    })

        if not amplify_stacks:
            raise ValueError(
                "No Amplify stacks found. Ensure 'npx ampx deploy' completed successfully."
            )

        # Sort by LastUpdatedTime (already have it from list_stacks)
        amplify_stacks.sort(key=lambda s: s['LastUpdatedTime'], reverse=True)
        stack_name = amplify_stacks[0]['StackName']

        log_info(f"Found Amplify stack: {stack_name}")

        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0].get('Outputs', [])

        if not outputs:
            raise ValueError(f"Amplify stack '{stack_name}' has no outputs")

        # Convert to dict
        output_dict = {}
        for item in outputs:
            output_dict[item['OutputKey']] = item['OutputValue']

        log_success(f"Retrieved {len(output_dict)} outputs from Amplify stack")
        return output_dict

    except Exception as e:
        log_error(f"Failed to get Amplify stack outputs: {e}")
        raise ValueError(f"Could not retrieve Amplify outputs: {e}") from e


def configure_ui(stack_name, region="us-east-1"):
    """Configure UI with stack outputs."""
    log_info("Configuring UI...")

    outputs = get_stack_outputs(stack_name, region)

    if not outputs:
        log_warning("No stack outputs found, skipping UI configuration")
        return outputs

    env_content = f"""REACT_APP_AWS_REGION={region}
REACT_APP_USER_POOL_ID={outputs.get('UserPoolId', '')}
REACT_APP_USER_POOL_CLIENT_ID={outputs.get('UserPoolClientId', '')}
REACT_APP_IDENTITY_POOL_ID={outputs.get('IdentityPoolId', '')}
REACT_APP_GRAPHQL_URL={outputs.get('GraphQLApiUrl', '')}
REACT_APP_INPUT_BUCKET={outputs.get('InputBucketName', '')}
"""

    env_file = Path("src/ui/.env.production")
    env_file.write_text(env_content)

    log_success(f"UI configuration written to {env_file}")

    return outputs


def print_outputs(outputs, project_name, region):
    """Print stack outputs in a nice format."""
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}Deployment Complete! (Project: {project_name}){Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

    print(f"{Colors.BOLD}Stack Outputs:{Colors.ENDC}\n")

    for key, value in outputs.items():
        print(f"{Colors.BOLD}{key}:{Colors.ENDC} {value}")

    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

    # Print UI URL if available
    if 'UIUrl' in outputs:
        print(f"{Colors.OKGREEN}UI URL:{Colors.ENDC} {outputs['UIUrl']}")
    elif 'CloudFrontDomain' in outputs:
        ui_url = f"https://{outputs['CloudFrontDomain']}"
        print(f"{Colors.OKGREEN}UI URL:{Colors.ENDC} {ui_url}")
    elif 'UIBucketName' in outputs:
        # Fallback to S3 website URL if CloudFront not configured
        ui_url = f"http://{outputs['UIBucketName']}.s3-website-{region}.amazonaws.com"
        print(f"{Colors.WARNING}UI URL (S3 - no HTTPS):{Colors.ENDC} {ui_url}")

    if 'GraphQLApiUrl' in outputs:
        print(f"{Colors.OKGREEN}GraphQL API:{Colors.ENDC} {outputs['GraphQLApiUrl']}")

    # Print Chat CDN URL if available
    if 'ChatCDN' in outputs:
        print(f"\n{Colors.OKGREEN}Chat Component:{Colors.ENDC}")
        print(f"CDN URL: {outputs['ChatCDN']}")
        print(f"\nEmbed on your website:")
        print(f'<script src="{outputs["ChatCDN"]}"></script>')
        print(f'<amplify-chat conversation-id="my-site"></amplify-chat>')

    if outputs.get('UserPoolId'):
        print(f"\n{Colors.OKGREEN}Next Steps:{Colors.ENDC}")
        print(f"1. Check your email for temporary password")
        print(f"2. Sign in to the UI and change your password")
        print(f"3. Upload a document to test the pipeline")

    print()


def extract_knowledge_base_id(stack_name, region):
    """
    Extract Bedrock Knowledge Base ID from SAM stack outputs.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region

    Returns:
        str: Knowledge Base ID

    Raises:
        ValueError: If KB ID not found in outputs
    """
    outputs = get_stack_outputs(stack_name, region)

    kb_id = outputs.get('KnowledgeBaseId')
    if not kb_id:
        raise ValueError(
            f"KnowledgeBaseId not found in stack outputs. "
            f"Ensure SAM stack '{stack_name}' is deployed and contains Bedrock Knowledge Base."
        )

    log_success(f"Found Knowledge Base ID: {kb_id}")
    return kb_id


def write_amplify_config(kb_id, region, config_table_name, source_bucket, source_key, user_pool_id, user_pool_client_id):
    """
    Generate TypeScript config file for Amplify backend.

    Creates amplify/data/config.ts with Knowledge Base ID, region,
    ConfigurationTable name, User Pool details, and web component source location.

    This config is imported by data/resource.ts and used by:
    - Conversation route (queries KB, reads config)
    - Lambda Authorizer (validates JWT tokens)
    - CodeBuild (downloads source from S3)

    Args:
        kb_id: Bedrock Knowledge Base ID
        region: AWS region
        config_table_name: DynamoDB ConfigurationTable name
        source_bucket: S3 bucket containing web component source
        source_key: S3 key of web component source zip
        user_pool_id: Cognito User Pool ID (from SAM stack)
        user_pool_client_id: Cognito User Pool Client ID (from SAM stack)

    Raises:
        IOError: If config file creation fails
    """
    config_content = f'''/**
 * Amplify Chat Backend Configuration
 *
 * This file is auto-generated by publish.py during deployment.
 * It contains the Knowledge Base ID from the SAM stack and AWS region configuration.
 *
 * DO NOT edit manually - changes will be overwritten on next deployment.
 */

export const KNOWLEDGE_BASE_CONFIG = {{
  // Bedrock Knowledge Base ID from SAM deployment
  // Retrieved from CloudFormation stack outputs
  knowledgeBaseId: "{kb_id}",

  // AWS Region where Bedrock Knowledge Base is deployed
  region: "{region}",

  // ConfigurationTable name for runtime config reading
  // Amplify Lambda reads chat settings from this table
  configurationTableName: "{config_table_name}",

  // Cognito User Pool (from SAM stack)
  // Used by Lambda Authorizer for JWT validation when requireAuth is enabled
  userPoolId: "{user_pool_id}",
  userPoolClientId: "{user_pool_client_id}",

  // Web component source location (for CodeBuild)
  // CodeBuild downloads and extracts this zip to build the component
  webComponentSourceBucket: "{source_bucket}",
  webComponentSourceKey: "{source_key}",
}} as const;

// Type-safe export for use in resource.ts
export type KnowledgeBaseConfig = typeof KNOWLEDGE_BASE_CONFIG;
'''

    config_file = Path('amplify/data/config.ts')
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(config_content)
    log_success(f"Amplify config written to {config_file}")


def write_amplify_env(kb_id, region):
    """
    Write Knowledge Base ID to .env.amplify for Amplify backend to use.

    Args:
        kb_id: Bedrock Knowledge Base ID
        region: AWS region
    """
    env_content = f"""# Amplify Chat Backend Environment Variables
# Generated by publish.py during SAM deployment

KNOWLEDGE_BASE_ID={kb_id}
AWS_REGION={region}
"""

    env_file = Path('.env.amplify')
    env_file.write_text(env_content)
    log_success(f"Amplify environment written to {env_file}")


def amplify_deploy(project_name, region, kb_id, artifact_bucket, config_table_name, user_pool_id, user_pool_client_id):
    """
    Deploy Amplify chat backend with web component CDN.

    This function:
    1. Packages web component source to S3
    2. Generates amplify/data/config.ts with KB ID, table name, User Pool, source location
    3. Deploys Amplify stack (GraphQL API, Lambda, CDN)
    4. Triggers CodeBuild to build and deploy web component
    5. Returns CDN URL for embedding

    Args:
        project_name: Project name for stack naming
        region: AWS region
        kb_id: Bedrock Knowledge Base ID (from SAM stack)
        artifact_bucket: S3 bucket for web component source
        config_table_name: DynamoDB ConfigurationTable name (from SAM stack)
        user_pool_id: Cognito User Pool ID (from SAM stack)
        user_pool_client_id: Cognito User Pool Client ID (from SAM stack)

    Returns:
        str: CDN URL for web component (https://d123.cloudfront.net/amplify-chat.js)

    Raises:
        subprocess.CalledProcessError: If deployment fails
        FileNotFoundError: If amplify/ directory not found
        IOError: If packaging or CodeBuild trigger fails
    """
    log_info("Deploying Amplify chat backend...")

    # Check if amplify directory exists
    amplify_dir = Path('amplify')
    if not amplify_dir.exists():
        raise FileNotFoundError(
            "Amplify project not found at amplify/. "
            "Ensure you're in the correct directory."
        )

    # Step 1: Package web component source
    log_info("Packaging web component source...")
    try:
        chat_source_key = package_amplify_chat_source(artifact_bucket, region)
        log_success(f"Web component source uploaded: s3://{artifact_bucket}/{chat_source_key}")
    except (FileNotFoundError, IOError) as e:
        log_error(f"Failed to package web component: {e}")
        raise

    # Step 2: Generate amplify/data/config.ts with all parameters
    log_info("Generating Amplify backend configuration...")
    try:
        write_amplify_config(
            kb_id,
            region,
            config_table_name,
            artifact_bucket,
            chat_source_key,
            user_pool_id,
            user_pool_client_id
        )
        write_amplify_env(kb_id, region)  # Also write .env.amplify
        log_success("Amplify configuration generated")
    except Exception as e:
        log_error(f"Failed to generate Amplify configuration: {e}")
        raise IOError(f"Config generation failed: {e}") from e

    # Step 3: Deploy Amplify stack
    log_info("Deploying Amplify stack (GraphQL API, Lambda, Cognito, CDN)...")
    log_info("This may take 10-15 minutes...")
    try:
        # Set environment variables for Amplify deployment
        # These are used by backend.ts to construct exact IAM resource ARNs
        deploy_env = os.environ.copy()
        deploy_env.update({
            'KNOWLEDGE_BASE_ID': kb_id,
            'AWS_REGION': region,
            'CONFIGURATION_TABLE_NAME': config_table_name,
            'WEB_COMPONENT_SOURCE_BUCKET': artifact_bucket,
            'WEB_COMPONENT_SOURCE_KEY': chat_source_key,
            'USER_POOL_ID': user_pool_id,
            'USER_POOL_CLIENT_ID': user_pool_client_id,
        })

        # Run deployment with environment variables
        result = subprocess.run(
            ['npx', 'ampx', 'deploy', '--yes'],
            cwd=str(Path.cwd()),
            env=deploy_env,
            check=True
        )

        log_success("Amplify stack deployed successfully")
    except subprocess.CalledProcessError as e:
        log_error(f"Amplify deployment failed: {e}")
        raise

    # Step 4: Get Amplify stack outputs
    log_info("Retrieving Amplify stack outputs...")
    try:
        outputs = get_amplify_stack_outputs(project_name, region)
        cdn_url = outputs.get('WebComponentCDN')
        build_project = outputs.get('BuildProjectName')

        if not cdn_url or not build_project:
            log_error("Missing required outputs from Amplify stack")
            log_error(f"Outputs: {outputs}")
            raise ValueError("Amplify stack outputs incomplete")

        log_info(f"CDN URL: {cdn_url}")
        log_info(f"Build Project: {build_project}")
    except Exception as e:
        log_error(f"Failed to retrieve Amplify outputs: {e}")
        raise IOError(f"Output retrieval failed: {e}") from e

    # Step 5: Trigger CodeBuild to build and deploy web component
    log_info("Triggering web component build and deployment...")
    build_id = None
    try:
        codebuild = boto3.client('codebuild', region_name=region)

        # Trigger build with source location (S3 format: s3://bucket/key)
        build_response = codebuild.start_build(
            projectName=build_project,
            sourceLocationOverride=f's3://{artifact_bucket}/{chat_source_key}',
            sourceTypeOverride='S3',
        )

        build_id = build_response['build']['id']
        log_info(f"Build started: {build_id}")
        log_info("Check CloudWatch Logs for build progress:")
        log_info(f"  https://console.aws.amazon.com/codesuite/codebuild/projects/{build_project}/build/{build_id}")

        # Poll build status for up to 2 minutes
        # If still running after timeout, continue without blocking deployment
        log_info("Checking build status (2 minute timeout)...")
        import time
        timeout_seconds = 120
        poll_interval = 10
        elapsed = 0

        while elapsed < timeout_seconds:
            time.sleep(poll_interval)
            elapsed += poll_interval

            build_status_response = codebuild.batch_get_builds(ids=[build_id])
            if build_status_response['builds']:
                status = build_status_response['builds'][0]['buildStatus']

                if status == 'SUCCEEDED':
                    log_success(f"Web component build completed successfully ({elapsed}s)")
                    break
                elif status in ['FAILED', 'FAULT', 'TIMED_OUT', 'STOPPED']:
                    log_error(f"Web component build failed with status: {status}")
                    log_warning("RECOVERY OPTIONS:")
                    log_warning(f"  1. Check build logs: https://console.aws.amazon.com/codesuite/codebuild/projects/{build_project}/build/{build_id}")
                    log_warning(f"  2. Manually trigger build: aws codebuild start-build --project-name {build_project}")
                    log_warning(f"  3. Redeploy with --chat-only flag")
                    break
                elif status == 'IN_PROGRESS':
                    log_info(f"Build still in progress... ({elapsed}s elapsed)")
                else:
                    log_warning(f"Unexpected build status: {status}")

        # If timeout reached and still running
        if elapsed >= timeout_seconds:
            log_warning("Build status check timed out after 2 minutes")
            log_warning("Build is still running in the background")
            log_warning(f"Monitor progress: https://console.aws.amazon.com/codesuite/codebuild/projects/{build_project}/build/{build_id}")

    except Exception as e:
        log_error(f"Failed to trigger CodeBuild: {e}")
        log_warning("Amplify stack deployed, but web component build failed")
        log_warning("RECOVERY OPTIONS:")
        log_warning(f"  1. Manually trigger build in CodeBuild console: {build_project}")
        log_warning(f"  2. Run: aws codebuild start-build --project-name {build_project}")
        log_warning(f"  3. Redeploy with --chat-only flag to retry")
        # Don't raise - stack is deployed successfully, just build failed

    # Step 6: Return CDN URL (even if build failed - it can be triggered manually)
    log_success(f"Amplify deployment complete! CDN URL: {cdn_url}")
    log_warning("Note: Web component may not be available at CDN URL until CodeBuild completes")
    return cdn_url


def seed_configuration_table(stack_name, region, chat_deployed=False, chat_cdn_url=''):
    """
    Seed ConfigurationTable with Schema and Default configurations.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        chat_deployed: Whether Amplify chat is deployed (default False)
        chat_cdn_url: CDN URL for web component (default '')
    """
    print(f"\n{Colors.HEADER}=== Seeding Configuration Table ==={Colors.ENDC}")

    # Get table name from CloudFormation outputs
    cfn = boto3.client('cloudformation', region_name=region)
    try:
        response = cfn.describe_stacks(StackName=stack_name)
        outputs = response['Stacks'][0]['Outputs']
        table_name = next(
            (o['OutputValue'] for o in outputs if o['OutputKey'] == 'ConfigurationTableName'),
            None
        )

        if not table_name:
            log_warning("ConfigurationTable not found in stack outputs")
            return

    except Exception as e:
        log_warning(f"Could not retrieve ConfigurationTable name: {e}")
        return

    log_info(f"Configuration Table: {table_name}")

    # Initialize DynamoDB
    dynamodb = boto3.resource('dynamodb', region_name=region)
    table = dynamodb.Table(table_name)

    # Define Schema
    schema_item = {
        'Configuration': 'Schema',
        'Schema': {
            'type': 'object',
            'required': ['ocr_backend'],
            'properties': {
                'ocr_backend': {
                    'type': 'string',
                    'order': 1,
                    'description': 'OCR backend to use for document processing',
                    'enum': ['textract', 'bedrock'],
                    'default': 'textract'
                },
                'bedrock_ocr_model_id': {
                    'type': 'string',
                    'order': 2,
                    'description': 'Bedrock model for OCR (only used if backend is bedrock)',
                    'enum': [
                        'meta.llama3-2-90b-instruct-v1:0',
                        'meta.llama3-2-11b-instruct-v1:0',
                        'us.anthropic.claude-sonnet-4-20250514-v1:0',
                        'us.anthropic.claude-haiku-4-5-20251001-v1:0'
                    ],
                    'dependsOn': {
                        'field': 'ocr_backend',
                        'value': 'bedrock'
                    }
                },
                'chat_model_id': {
                    'type': 'string',
                    'order': 3,
                    'description': 'Bedrock model for Knowledge Base chat queries',
                    'enum': [
                        'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                        'us.anthropic.claude-sonnet-4-20250514-v1:0',
                        'us.amazon.nova-pro-v1:0',
                        'us.amazon.nova-lite-v1:0',
                        'us.amazon.nova-micro-v1:0'
                    ],
                    'default': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
                },
                'chat_require_auth': {
                    'type': 'boolean',
                    'order': 4,
                    'description': 'Require authentication for chat access',
                    'default': False
                },
                'chat_primary_model': {
                    'type': 'string',
                    'order': 5,
                    'description': 'Primary Bedrock model for chat (before quota limits)',
                    'enum': [
                        'us.anthropic.claude-sonnet-4-20250514-v1:0',
                        'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                        'us.amazon.nova-pro-v1:0',
                        'us.amazon.nova-lite-v1:0'
                    ],
                    'default': 'us.anthropic.claude-haiku-4-5-20251001-v1:0'
                },
                'chat_fallback_model': {
                    'type': 'string',
                    'order': 6,
                    'description': 'Fallback model when quotas exceeded',
                    'enum': [
                        'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                        'us.amazon.nova-micro-v1:0',
                        'us.amazon.nova-lite-v1:0'
                    ],
                    'default': 'us.amazon.nova-micro-v1:0'
                },
                'chat_global_quota_daily': {
                    'type': 'number',
                    'order': 7,
                    'description': 'Max messages per day (all users combined) on primary model',
                    'default': 10000
                },
                'chat_per_user_quota_daily': {
                    'type': 'number',
                    'order': 8,
                    'description': 'Max messages per user per day on primary model',
                    'default': 100
                },
                'chat_theme_preset': {
                    'type': 'string',
                    'order': 9,
                    'description': 'UI theme preset',
                    'enum': ['light', 'dark', 'brand'],
                    'default': 'light'
                },
                'chat_theme_overrides': {
                    'type': 'object',
                    'order': 10,
                    'description': 'Custom theme overrides (optional)',
                    'properties': {
                        'primaryColor': {'type': 'string'},
                        'fontFamily': {'type': 'string'},
                        'spacing': {
                            'type': 'string',
                            'enum': ['compact', 'comfortable', 'spacious']
                        }
                    }
                },
                'chat_cdn_url': {
                    'type': 'string',
                    'order': 11,
                    'description': 'Web component CDN URL (read-only)',
                    'readOnly': True
                }
            }
        }
    }

    # Define Default configuration
    default_item = {
        'Configuration': 'Default',
        'chat_deployed': chat_deployed,
        'chat_cdn_url': chat_cdn_url,
        'ocr_backend': 'textract',
        'bedrock_ocr_model_id': 'meta.llama3-2-90b-instruct-v1:0',
        'chat_model_id': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        'chat_require_auth': False,
        'chat_primary_model': 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
        'chat_fallback_model': 'us.amazon.nova-micro-v1:0',
        'chat_global_quota_daily': 10000,
        'chat_per_user_quota_daily': 100,
        'chat_theme_preset': 'light',
        'chat_theme_overrides': {}
    }

    try:
        # Put Schema
        log_info("Seeding Schema configuration...")
        table.put_item(Item=schema_item)
        log_success("Schema seeded")

        # Put Default
        log_info("Seeding Default configuration...")
        table.put_item(Item=default_item)
        log_success("Default seeded")

        log_success("Configuration table seeded successfully\n")

    except Exception as e:
        log_warning(f"Error seeding configuration table: {e}\n")


def main():
    """
    Main execution function.

    Integration Tests Verified:
    - Missing required arguments (--project-name, --admin-email, --region) fail appropriately
    - Invalid project name validation (uppercase, special chars, too short/long)
    - Invalid email validation
    - Invalid region validation (format check with regex)
    - --skip-ui flag works correctly
    - Prerequisite checks execute in correct order
    - All inputs validated before AWS operations begin
    """
    parser = argparse.ArgumentParser(
        description="Deploy RAGStack-Lambda with project-based naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python publish.py --project-name customer-docs --admin-email admin@example.com --region us-east-1
  python publish.py --project-name legal-archive --admin-email admin@example.com --region us-west-2 --skip-ui
        """
    )

    parser.add_argument(
        "--project-name",
        required=True,
        help="Project name (lowercase alphanumeric + hyphens, 2-32 chars, must start with letter)"
    )

    parser.add_argument(
        "--admin-email",
        required=True,
        help="Admin email for Cognito user and CloudWatch alerts"
    )

    parser.add_argument(
        "--region",
        required=True,
        help="AWS region (e.g., us-east-1, us-west-2)"
    )

    parser.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip UI build and deployment"
    )

    parser.add_argument(
        "--deploy-chat",
        action="store_true",
        help="Deploy both SAM core and Amplify chat backend together"
    )

    parser.add_argument(
        "--chat-only",
        action="store_true",
        help="Deploy Amplify chat backend only (assumes SAM core already deployed)"
    )

    args = parser.parse_args()

    try:
        print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}RAGStack-Lambda Deployment{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

        # Validate conflicting flags
        if args.deploy_chat and args.chat_only:
            log_error("Cannot use both --deploy-chat and --chat-only")
            sys.exit(1)

        # Validate inputs
        log_info("Validating inputs...")
        try:
            validate_project_name(args.project_name)
            validate_region(args.region)
            if not validate_email(args.admin_email):
                log_error(f"Invalid email format: {args.admin_email}")
                sys.exit(1)
        except ValueError as e:
            log_error(str(e))
            sys.exit(1)

        log_success("All inputs validated")

        # Log deployment mode
        if args.chat_only:
            log_info("Mode: Amplify chat deployment only (SAM core assumed deployed)")
        elif args.deploy_chat:
            log_info("Mode: SAM core + Amplify chat deployment")
        else:
            log_info("Mode: SAM core deployment only")

        log_info(f"Project Name: {args.project_name}")
        log_info(f"Admin Email: {args.admin_email}")
        log_info(f"Region: {args.region}")

        # =====================================================================
        # Chat-only deployment path (Amplify only)
        # =====================================================================
        if args.chat_only:
            log_info("Starting Amplify chat-only deployment...")

            # Check prerequisites (lighter check for chat-only)
            log_info("Checking prerequisites...")
            check_python_version()
            check_aws_cli()
            log_success("Prerequisites met")

            # Get KB ID and ConfigurationTable name from existing SAM stack
            stack_name = f"RAGStack-{args.project_name}"
            try:
                kb_id = extract_knowledge_base_id(stack_name, args.region)

                # Get ConfigurationTable name, artifact bucket, and User Pool from SAM outputs
                sam_outputs = get_stack_outputs(stack_name, args.region)
                config_table_name = sam_outputs.get('ConfigurationTableName')
                artifact_bucket = sam_outputs.get('ArtifactBucketName')
                user_pool_id = sam_outputs.get('UserPoolId')
                user_pool_client_id = sam_outputs.get('UserPoolClientId')

                if not config_table_name:
                    log_error("ConfigurationTableName not found in SAM stack outputs")
                    sys.exit(1)

                if not artifact_bucket:
                    log_error("ArtifactBucketName not found in SAM stack outputs")
                    sys.exit(1)

                if not user_pool_id or not user_pool_client_id:
                    log_error("UserPoolId or UserPoolClientId not found in SAM stack outputs")
                    sys.exit(1)

                log_info(f"Knowledge Base ID: {kb_id}")
                log_info(f"Configuration Table: {config_table_name}")
                log_info(f"Artifact Bucket: {artifact_bucket}")
                log_info(f"User Pool ID: {user_pool_id}")

            except ValueError as e:
                log_error(str(e))
                sys.exit(1)

            # Deploy Amplify
            try:
                cdn_url = amplify_deploy(
                    args.project_name,
                    args.region,
                    kb_id,
                    artifact_bucket,
                    config_table_name,
                    user_pool_id,
                    user_pool_client_id
                )

                # Update chat_deployed flag and CDN URL
                seed_configuration_table(stack_name, args.region, chat_deployed=True, chat_cdn_url=cdn_url)

                log_success(f"Chat CDN URL: {cdn_url}")
            except Exception as e:
                log_error(f"Amplify deployment failed: {e}")
                sys.exit(1)

            log_success("Amplify chat backend deployed successfully!")
            sys.exit(0)

        # =====================================================================
        # SAM deployment path (core only or core + chat)
        # =====================================================================

        # Check full prerequisites
        log_info("Checking prerequisites...")
        check_python_version()
        check_nodejs_version(skip_ui=args.skip_ui)
        check_aws_cli()
        check_sam_cli()
        log_success("All prerequisites met")

        # Create artifact bucket first
        try:
            artifact_bucket = create_sam_artifact_bucket(args.project_name, args.region)
        except IOError as e:
            log_error(f"Failed to create artifact bucket: {e}")
            sys.exit(1)

        # Package UI source (unless --skip-ui)
        ui_source_key = None
        if not args.skip_ui:
            try:
                ui_source_key = package_ui_source(artifact_bucket, args.region)
                log_info(f"UI source uploaded to {artifact_bucket}/{ui_source_key}")
            except (FileNotFoundError, IOError) as e:
                log_error(f"Failed to package UI: {e}")
                sys.exit(1)

        # SAM build
        sam_build()

        # Check for failed stack and clean up if needed
        stack_name = f"RAGStack-{args.project_name}"
        try:
            handle_failed_stack(stack_name, args.region)
        except IOError as e:
            log_error(f"Failed to handle existing stack: {e}")
            sys.exit(1)

        # SAM deploy with UI parameters
        stack_name = sam_deploy(
            args.project_name,
            args.admin_email,
            args.region,
            artifact_bucket,
            ui_source_key=ui_source_key,
            skip_ui=args.skip_ui
        )

        # Get outputs
        outputs = get_stack_outputs(stack_name, args.region)

        # Seed configuration table
        seed_configuration_table(stack_name, args.region)

        # Configure UI
        if not args.skip_ui:
            configure_ui(stack_name, args.region)

        # Print outputs
        print_outputs(outputs, args.project_name, args.region)

        # =====================================================================
        # Deploy Amplify chat if requested
        # =====================================================================
        if args.deploy_chat:
            log_info("SAM deployment complete. Now deploying Amplify chat backend...")

            # Extract KB ID and ConfigurationTable name from SAM outputs
            try:
                kb_id = extract_knowledge_base_id(stack_name, args.region)

                # Get ConfigurationTable name and User Pool from SAM outputs
                sam_outputs = get_stack_outputs(stack_name, args.region)
                config_table_name = sam_outputs.get('ConfigurationTableName')
                user_pool_id = sam_outputs.get('UserPoolId')
                user_pool_client_id = sam_outputs.get('UserPoolClientId')

                if not config_table_name:
                    raise ValueError("ConfigurationTableName not found in SAM stack outputs")

                if not user_pool_id or not user_pool_client_id:
                    raise ValueError("UserPoolId or UserPoolClientId not found in SAM stack outputs")

                log_info(f"Knowledge Base ID: {kb_id}")
                log_info(f"Configuration Table: {config_table_name}")
                log_info(f"User Pool ID: {user_pool_id}")

            except ValueError as e:
                log_error(str(e))
                log_warning("Chat deployment skipped due to missing SAM outputs")
                sys.exit(0)

            # Deploy Amplify
            try:
                # Set chat_deployed=True BEFORE Amplify deploy to avoid race condition
                # If deploy fails, flag is set but no harm (chat won't work, but UI shows it)
                log_info("Marking chat as deployed in configuration...")
                seed_configuration_table(stack_name, args.region, chat_deployed=True)

                cdn_url = amplify_deploy(
                    args.project_name,
                    args.region,
                    kb_id,
                    artifact_bucket,
                    config_table_name,
                    user_pool_id,
                    user_pool_client_id
                )

                # Update configuration with CDN URL now that deployment succeeded
                log_info("Updating configuration with CDN URL...")
                seed_configuration_table(stack_name, args.region, chat_deployed=True, chat_cdn_url=cdn_url)

                log_success("Amplify chat backend deployed successfully!")
                log_success(f"Chat CDN URL: {cdn_url}")

                # Add CDN URL to outputs for final display
                outputs['ChatCDN'] = cdn_url

            except Exception as e:
                log_error(f"Amplify deployment failed: {e}")
                log_warning("SAM core is deployed, but chat backend deployment failed")
                log_warning("Note: chat_deployed flag was set but deployment failed")
                log_warning("  Admins may see chat settings UI, but functionality won't work")
                log_warning("  To fix: Retry deployment or manually set chat_deployed=false in DynamoDB")
                sys.exit(1)

        log_success("Deployment complete!")

    except subprocess.CalledProcessError as e:
        log_error(f"Command failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        log_warning("\nDeployment cancelled by user")
        sys.exit(1)
    except Exception as e:
        log_error(f"Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
