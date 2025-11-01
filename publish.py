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
    Check if Node.js 18+ and npm are available.

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
        log_info("Install Node.js 18+ from: https://nodejs.org/")
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

        if node_major < 18:
            log_error(f"Node.js {node_version} found, but 18+ is required for UI build")
            log_info("Please upgrade Node.js to version 18 or later")
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
                        'MaxAttempts': 120  # Wait up to 1 hour (120 * 30s)
                    }
                )
                log_success(f"Stack '{stack_name}' deleted successfully")
                return True
            except Exception as e:
                log_warning(f"Stack deletion timed out or failed: {e}")
                log_warning(f"You may need to manually delete the stack or clean up resources")
                return True  # Return True to allow proceeding even if deletion times out

        # Check if stack is in a failed/rollback state
        if stack_status in ['ROLLBACK_COMPLETE', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_ROLLBACK_COMPLETE', 'ROLLBACK_FAILED']:
            log_warning(f"Stack '{stack_name}' is in {stack_status} state")
            log_info(f"Deleting failed stack '{stack_name}'...")

            try:
                cf_client.delete_stack(StackName=stack_name)

                # Wait for deletion to complete with longer timeout
                waiter = cf_client.get_waiter('stack_delete_complete')
                log_info("Waiting for stack deletion to complete (this may take several minutes)...")
                waiter.wait(
                    StackName=stack_name,
                    WaiterConfig={
                        'Delay': 30,  # Check every 30 seconds
                        'MaxAttempts': 120  # Wait up to 1 hour (120 * 30s)
                    }
                )

                log_success(f"Stack '{stack_name}' deleted successfully")
                return True
            except Exception as e:
                log_warning(f"Stack deletion timed out: {e}")
                log_warning(f"Stack may still be deleting in the background. You can check CloudFormation console.")
                return True  # Return True to allow proceeding

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


def cleanup_orphaned_resources(project_name, region):
    """
    Clean up orphaned AWS resources from failed deployments.

    Since CloudFormation resources now use deployment-unique suffixes, this function
    only needs to handle CloudFront distributions that may be stuck in enabled state
    from a previous deployment.

    Args:
        project_name: Project name for resource naming
        region: AWS region

    Raises:
        IOError: If cleanup fails
    """
    log_info("Checking for any stuck CloudFront distributions from previous deployments...")

    # Clean up CloudFront distributions (which can get stuck in DELETE_IN_PROGRESS)
    cloudfront_client = boto3.client('cloudfront')

    try:
        # List all distributions
        paginator = cloudfront_client.get_paginator('list_distributions')
        for page in paginator.paginate():
            if 'DistributionList' not in page or 'Items' not in page.get('DistributionList', {}):
                continue

            items = page.get('DistributionList', {}).get('Items', [])
            for distribution in items:
                # Check if this distribution belongs to our project
                comment = distribution.get('Comment', '')
                if project_name in comment:
                    dist_id = distribution['Id']
                    is_enabled = distribution.get('Enabled', False)

                    if is_enabled:
                        log_warning(f"Found enabled CloudFront distribution {dist_id} for project {project_name}")
                        log_info(f"Disabling distribution: {dist_id}")

                        try:
                            # Get current distribution config
                            dist_config = cloudfront_client.get_distribution_config(Id=dist_id)
                            config = dist_config.get('DistributionConfig', {})
                            etag = dist_config.get('ETag', '')

                            if not config or not etag:
                                log_warning(f"Could not get config for distribution {dist_id}")
                                continue

                            # Disable the distribution
                            config['Enabled'] = False
                            cloudfront_client.update_distribution(
                                Id=dist_id,
                                DistributionConfig=config,
                                IfMatch=etag
                            )

                            log_success(f"Disabled CloudFront distribution: {dist_id}")

                            # Get fresh ETag after disabling
                            dist_config = cloudfront_client.get_distribution_config(Id=dist_id)
                            etag = dist_config.get('ETag', '')

                            # Try to delete it
                            if etag:
                                log_info(f"Deleting distribution: {dist_id}")
                                cloudfront_client.delete_distribution(Id=dist_id, IfMatch=etag)
                                log_success(f"Deleted CloudFront distribution: {dist_id}")

                        except Exception as e:
                            log_warning(f"Failed to delete CloudFront distribution {dist_id}: {e}")
                            log_warning(f"Distribution may need to be manually deleted from CloudFront console")

    except Exception as e:
        log_warning(f"Error cleaning up CloudFront distributions: {e}")


def cleanup_stuck_cloudfront_distributions(project_name):
    """
    Clean up any CloudFront distributions that are stuck or enabled for the project.

    This is called before deployment to ensure a clean slate. Distributions that are
    enabled will be disabled, and disabled ones will be deleted.

    Args:
        project_name: Project name to match against distribution comments
    """
    log_info("Checking for CloudFront distributions from previous deployments...")
    cloudfront_client = boto3.client('cloudfront')

    try:
        paginator = cloudfront_client.get_paginator('list_distributions')
        for page in paginator.paginate():
            distribution_list = page.get('DistributionList', {})
            if not distribution_list or 'Items' not in distribution_list:
                continue

            for distribution in distribution_list.get('Items', []):
                comment = distribution.get('Comment', '')
                if project_name in comment:
                    dist_id = distribution['Id']
                    status = distribution.get('Status', '')
                    is_enabled = distribution.get('Enabled', False)

                    log_warning(f"Found distribution {dist_id} (status: {status}, enabled: {is_enabled})")

                    # If distribution is disabled, we can delete it
                    if not is_enabled:
                        try:
                            dist_config = cloudfront_client.get_distribution_config(Id=dist_id)
                            config = dist_config.get('DistributionConfig', {})
                            etag = dist_config.get('ETag', '')

                            if not etag:
                                log_warning(f"Could not get ETag for distribution {dist_id}")
                                continue

                            log_info(f"Deleting disabled distribution: {dist_id}")
                            cloudfront_client.delete_distribution(Id=dist_id, IfMatch=etag)
                            log_success(f"Deleted CloudFront distribution: {dist_id}")
                        except ClientError as e:
                            error_code = e.response.get('Error', {}).get('Code', '')
                            # If distribution is still being deleted, that's OK - continue
                            if 'InvalidIfMatchVersion' in error_code or 'DistributionNotDisabled' in error_code:
                                log_warning(f"Distribution {dist_id} is still propagating - will retry later")
                            else:
                                log_warning(f"Could not delete distribution {dist_id}: {e}")
                        except Exception as e:
                            log_warning(f"Unexpected error deleting distribution {dist_id}: {e}")
                    # If still enabled, disable it (this is the normal case)
                    elif is_enabled:
                        try:
                            dist_config = cloudfront_client.get_distribution_config(Id=dist_id)
                            config = dist_config.get('DistributionConfig', {})
                            etag = dist_config.get('ETag', '')

                            if not config or not etag:
                                log_warning(f"Could not get config for distribution {dist_id}")
                                continue

                            config['Enabled'] = False
                            cloudfront_client.update_distribution(
                                Id=dist_id,
                                DistributionConfig=config,
                                IfMatch=etag
                            )
                            log_warning(f"Disabled CloudFront distribution {dist_id}")
                        except Exception as e:
                            log_warning(f"Could not disable distribution {dist_id}: {e}")

    except Exception as e:
        log_warning(f"Error checking CloudFront distributions: {e}")


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

    # Generate unique deployment suffix (5 lowercase alphanumeric chars)
    import random
    import string
    deployment_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
    log_info(f"Generated deployment suffix: {deployment_suffix}")

    # Base parameter overrides
    param_overrides = [
        f"DeploymentSuffix={deployment_suffix}",
        f"ProjectName={project_name}",
        f"AdminEmail={admin_email}",
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


def build_ui():
    """Build React UI."""
    log_info("Building UI...")

    ui_dir = Path("src/ui")

    if not ui_dir.exists():
        log_warning("UI directory not found, skipping UI build")
        return

    # Install dependencies
    log_info("Installing UI dependencies...")
    run_command(["npm", "install"], cwd=ui_dir)

    # Build
    log_info("Building production UI...")
    run_command(["npm", "run", "build"], cwd=ui_dir)

    log_success("UI build complete")


def deploy_ui(ui_bucket, region="us-east-1"):
    """Deploy UI to S3."""
    log_info(f"Deploying UI to {ui_bucket}...")

    ui_build_dir = Path("src/ui/build")

    if not ui_build_dir.exists():
        log_error("UI build directory not found. Run build first.")
        return

    # Sync build to S3
    run_command([
        "aws", "s3", "sync",
        str(ui_build_dir),
        f"s3://{ui_bucket}/",
        "--delete",
        "--region", region
    ])

    log_success("UI deployed to S3")


def invalidate_cloudfront(distribution_id):
    """Invalidate CloudFront cache."""
    log_info(f"Invalidating CloudFront cache for distribution {distribution_id}...")

    run_command([
        "aws", "cloudfront", "create-invalidation",
        "--distribution-id", distribution_id,
        "--paths", "/*"
    ])

    log_success("CloudFront cache invalidation initiated")


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

    if outputs.get('UserPoolId'):
        print(f"\n{Colors.OKGREEN}Next Steps:{Colors.ENDC}")
        print(f"1. Check your email for temporary password")
        print(f"2. Sign in to the UI and change your password")
        print(f"3. Upload a document to test the pipeline")

    print()


def seed_configuration_table(stack_name, region):
    """
    Seed ConfigurationTable with Schema and Default configurations.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
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
            'required': ['ocr_backend', 'text_embed_model_id'],
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
                        'anthropic.claude-3-5-haiku-20241022-v1:0',
                        'anthropic.claude-3-5-sonnet-20241022-v2:0',
                        'anthropic.claude-3-haiku-20240307-v1:0',
                        'anthropic.claude-3-sonnet-20240229-v1:0'
                    ],
                    'dependsOn': {
                        'field': 'ocr_backend',
                        'value': 'bedrock'
                    }
                },
                'text_embed_model_id': {
                    'type': 'string',
                    'order': 3,
                    'description': 'Bedrock model for text embeddings',
                    'enum': [
                        'amazon.titan-embed-text-v2:0',
                        'amazon.titan-embed-text-v1',
                        'cohere.embed-english-v3',
                        'cohere.embed-multilingual-v3'
                    ],
                    'default': 'amazon.titan-embed-text-v2:0'
                },
                'image_embed_model_id': {
                    'type': 'string',
                    'order': 4,
                    'description': 'Bedrock model for image embeddings',
                    'enum': [
                        'amazon.titan-embed-image-v1'
                    ],
                    'default': 'amazon.titan-embed-image-v1'
                },
                'response_model_id': {
                    'type': 'string',
                    'order': 5,
                    'description': 'Bedrock model for Knowledge Base query responses',
                    'enum': [
                        'anthropic.claude-3-5-sonnet-20241022-v2:0',
                        'anthropic.claude-3-5-haiku-20241022-v1:0',
                        'anthropic.claude-3-opus-20240229-v1:0'
                    ],
                    'default': 'anthropic.claude-3-5-haiku-20241022-v1:0'
                }
            }
        }
    }

    # Define Default configuration
    default_item = {
        'Configuration': 'Default',
        'ocr_backend': 'textract',
        'bedrock_ocr_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0',
        'text_embed_model_id': 'amazon.titan-embed-text-v2:0',
        'image_embed_model_id': 'amazon.titan-embed-image-v1',
        'response_model_id': 'anthropic.claude-3-5-haiku-20241022-v1:0'
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

    args = parser.parse_args()

    try:
        print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}RAGStack-Lambda Deployment{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

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

        # Check prerequisites
        log_info("Checking prerequisites...")
        check_python_version()
        check_nodejs_version(skip_ui=args.skip_ui)
        check_aws_cli()
        check_sam_cli()
        log_success("All prerequisites met")

        log_info(f"Project Name: {args.project_name}")
        log_info(f"Admin Email: {args.admin_email}")
        log_info(f"Region: {args.region}")

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
            # First, check for any stuck CloudFront distributions and disable them
            cleanup_stuck_cloudfront_distributions(args.project_name)

            handle_failed_stack(stack_name, args.region)
            # Also clean up orphaned resources from failed deployments
            cleanup_orphaned_resources(args.project_name, args.region)
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

        # Configure and deploy UI
        if not args.skip_ui:
            configure_ui(stack_name, args.region)
            build_ui()

            if 'UIBucketName' in outputs:
                deploy_ui(outputs['UIBucketName'], args.region)

                # Invalidate CloudFront if available
                if 'CloudFrontDistributionId' in outputs:
                    invalidate_cloudfront(outputs['CloudFrontDistributionId'])

        # Print outputs
        print_outputs(outputs, args.project_name, args.region)

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
