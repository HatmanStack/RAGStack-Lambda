#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
RAGStack-Lambda Deployment Script

Project-based deployment automation for RAGStack-Lambda stack.

Usage:
    python publish.py --project-name customer-docs --admin-email admin@example.com
    python publish.py --project-name legal-archive --admin-email admin@example.com --skip-ui
"""

import argparse
import os
import re
import subprocess
import sys
import time
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
        log_info(f"Current version: Python {version_info[0]}.{version_info[1]}.{version_info[2]}")
        sys.exit(1)

    if version_info[0] == 3 and version_info[1] < 12:
        log_error("Python 3.12+ is required")
        log_info(f"Current version: Python {version_info[0]}.{version_info[1]}.{version_info[2]}")
        log_info("Please upgrade Python and try again")
        sys.exit(1)

    log_success(f"Found Python {version_info[0]}.{version_info[1]}.{version_info[2]}")
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
    # Note: Removed --cached flag to ensure template.yaml changes (like BuildSpec updates)
    # are always included in the build output, even when Lambda code hasn't changed
    run_command(["sam", "build", "--parallel"])
    log_success("SAM build complete")


def handle_failed_stack(stack_name, region):
    """
    Check if stack exists and is in an unrecoverable state.

    Only deletes stacks that cannot be updated (creation failures like ROLLBACK_COMPLETE).
    UPDATE_ROLLBACK_COMPLETE is NOT deleted as it's a healthy state that can be updated.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region

    Returns:
        bool: True if stack was deleted or doesn't exist, False if stack exists and is healthy

    Raises:
        OSError: If deletion fails
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
                log_error("  1. Check CloudFormation console: https://console.aws.amazon.com/cloudformation")
                log_error(f"  2. Or run: aws cloudformation wait stack-delete-complete --stack-name {stack_name}")
                log_error("  3. Then retry this deployment")
                raise OSError(f"Stack deletion timeout - stack '{stack_name}' may still be deleting") from e

        # Check if stack is in an unrecoverable state (creation failures only)
        # UPDATE_ROLLBACK_COMPLETE is healthy and can be updated again
        if stack_status in ['ROLLBACK_COMPLETE', 'CREATE_FAILED', 'DELETE_FAILED', 'ROLLBACK_FAILED']:
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
                log_error("  1. Check CloudFormation console: https://console.aws.amazon.com/cloudformation")
                log_error(f"  2. Or run: aws cloudformation describe-stacks --stack-name {stack_name}")
                log_error(f"  3. If stuck, manually delete: aws cloudformation delete-stack --stack-name {stack_name}")
                log_error("  4. Then retry this deployment")
                raise OSError(f"Stack deletion timeout - cannot proceed while stack '{stack_name}' may still be deleting") from e

        # Stack exists and is in a healthy state
        return False

    except cf_client.exceptions.ClientError as e:
        error_code = e.response['Error']['Code']

        # Stack doesn't exist - this is fine, we can proceed
        if error_code == 'ValidationError' and 'does not exist' in str(e):
            log_info(f"Stack '{stack_name}' does not exist, proceeding with fresh deployment")
            return True

        # Other errors should be raised
        raise OSError(f"Failed to check stack status: {e}") from e


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
        OSError: If bucket creation fails
    """
    s3_client = boto3.client('s3', region_name=region)
    sts_client = boto3.client('sts', region_name=region)

    # Get account ID for bucket naming
    try:
        account_id = sts_client.get_caller_identity()['Account']
    except ClientError as e:
        raise OSError(f"Failed to get AWS account ID: {e}") from e

    # Use project-specific bucket for all deployment artifacts
    bucket_name = f'{project_name}-artifacts-{account_id}'

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
                raise OSError(f"Failed to create S3 bucket {bucket_name}: {create_error}") from create_error
        else:
            raise OSError(f"Failed to access S3 bucket {bucket_name}: {e}") from e

    return bucket_name


def sam_deploy(project_name, admin_email, region, artifact_bucket, ui_source_key=None, wc_source_key=None, skip_ui=False):
    """
    Deploy SAM application with project-based naming.

    Args:
        project_name: Project name for resource naming
        admin_email: Admin email for Cognito and alerts
        region: AWS region
        artifact_bucket: S3 bucket for SAM artifacts and UI source
        ui_source_key: S3 key for UI source zip (if not skip_ui)
        wc_source_key: S3 key for web component source zip
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

    # Add web component source key if provided
    if wc_source_key:
        log_info("Web component will be deployed via CodeBuild during stack creation")
        param_overrides.append(f"WebComponentSourceKey={wc_source_key}")

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


def _package_source_to_s3(source_dir, bucket_name, region, exclude_dirs, archive_prefix, s3_key_prefix):
    """
    Shared implementation for packaging source code and uploading to S3.

    Args:
        source_dir: Path to source directory to package
        bucket_name: S3 bucket name to upload to
        region: AWS region for bucket operations
        exclude_dirs: List of directory names to exclude from zip
        archive_prefix: Path prefix inside zip archive (e.g., 'ui' or 'web-component')
        s3_key_prefix: Prefix for S3 key (e.g., 'ui-source' or 'web-component-source')

    Returns:
        str: S3 key of uploaded source zip

    Raises:
        FileNotFoundError: If source directory doesn't exist
        OSError: If packaging or upload fails
    """
    import tempfile
    import time
    import zipfile
    from pathlib import Path

    source_path = Path(source_dir)
    if not source_path.exists():
        raise FileNotFoundError(f"Source directory not found: {source_path}")

    # Create temporary zip file
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp_file:
        zip_path = tmp_file.name

    try:
        # Create zip file with exclusions
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    # Skip excluded directories
                    if any(excluded in file_path.parts for excluded in exclude_dirs):
                        continue

                    # Store with specified archive prefix
                    if archive_prefix:
                        arcname = Path(archive_prefix) / file_path.relative_to(source_path)
                    else:
                        # Include parent directory in zip (e.g., src/ui becomes ui/*)
                        arcname = file_path.relative_to(source_path.parent)
                    zipf.write(file_path, arcname)

        # Upload to S3
        s3_client = boto3.client('s3', region_name=region)
        timestamp = int(time.time())
        key = f'{s3_key_prefix}-{timestamp}.zip'

        log_info(f"Uploading to s3://{bucket_name}/{key}...")
        try:
            s3_client.upload_file(zip_path, bucket_name, key)
        except ClientError as e:
            raise OSError(f"Failed to upload source to S3: {e}") from e

        # Clean up temporary file
        os.remove(zip_path)

        return key

    except (OSError, FileNotFoundError):
        # Re-raise expected exceptions
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise
    except Exception as e:
        # Clean up temporary file on unexpected error
        if os.path.exists(zip_path):
            os.remove(zip_path)
        raise OSError(f"Unexpected error packaging source: {e}") from e


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
        OSError: If packaging or upload fails
    """
    log_info("Packaging UI source code...")

    key = _package_source_to_s3(
        source_dir='src/ui',
        bucket_name=bucket_name,
        region=region,
        exclude_dirs=['node_modules', 'build'],
        archive_prefix=None,  # Keep original structure (ui/* in zip)
        s3_key_prefix='ui-source'
    )

    log_success("UI source uploaded to S3")
    return key


def package_ragstack_chat_source(bucket_name, region):
    """
    Package RagStack chat web component source code as zip and upload to S3.

    Creates a zip file of src/ragstack-chat/ (excluding node_modules and dist),
    uploads it to the provided S3 bucket, and returns the S3 key for CodeBuild.

    Args:
        bucket_name: S3 bucket name to upload to
        region: AWS region for bucket operations

    Returns:
        str: S3 key of uploaded web component source zip

    Raises:
        FileNotFoundError: If src/ragstack-chat/ doesn't exist
        OSError: If packaging or upload fails
    """
    log_info("Packaging RagStack chat web component source...")

    key = _package_source_to_s3(
        source_dir='src/ragstack-chat',
        bucket_name=bucket_name,
        region=region,
        exclude_dirs=['node_modules', 'dist'],
        archive_prefix='src/ragstack-chat',  # CodeBuild BuildSpec does 'cd src/ragstack-chat'
        s3_key_prefix='web-component-source'
    )

    log_success("RagStack chat web component source uploaded to S3")
    return key


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
REACT_APP_DATA_BUCKET={outputs.get('DataBucketName', '')}
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
        print("\nEmbed on your website:")
        print(f'<script src="{outputs["ChatCDN"]}"></script>')
        print('<ragstack-chat conversation-id="my-site"></ragstack-chat>')

    if outputs.get('UserPoolId'):
        print(f"\n{Colors.OKGREEN}Next Steps:{Colors.ENDC}")
        print("1. Check your email for temporary password")
        print("2. Sign in to the UI and change your password")
        print("3. Upload a document to test the pipeline")

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


def get_existing_chat_config(table_name, region):
    """
    Get existing chat configuration from DynamoDB table.

    Args:
        table_name: DynamoDB table name
        region: AWS region

    Returns:
        tuple: (chat_deployed: bool, chat_cdn_url: str)
               Returns (False, '') if configuration doesn't exist
    """
    try:
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table = dynamodb.Table(table_name)

        # Get Default configuration item
        response = table.get_item(Key={'Configuration': 'Default'})

        if 'Item' in response:
            item = response['Item']
            chat_deployed = item.get('chat_deployed', False)
            chat_cdn_url = item.get('chat_cdn_url', '')
            log_info(f"Found existing chat config: deployed={chat_deployed}, cdn_url={chat_cdn_url[:50] if chat_cdn_url else 'none'}")
            return (chat_deployed, chat_cdn_url)

    except Exception as e:
        log_info(f"No existing chat config found: {e}")

    return (False, '')


def seed_configuration_table(stack_name, region, chat_cdn_url=''):
    """
    Seed ConfigurationTable with Schema and Default configurations.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
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
                },
                'chat_allow_document_access': {
                    'type': 'boolean',
                    'order': 12,
                    'description': 'Allow users to download original source documents via presigned URLs',
                    'default': False
                },
                'public_access_chat': {
                    'type': 'boolean',
                    'order': 13,
                    'description': 'Allow unauthenticated chat queries (web component)',
                    'default': True
                },
                'public_access_search': {
                    'type': 'boolean',
                    'order': 14,
                    'description': 'Allow unauthenticated search queries',
                    'default': True
                },
                'public_access_upload': {
                    'type': 'boolean',
                    'order': 15,
                    'description': 'Allow unauthenticated document uploads',
                    'default': False
                },
                'public_access_image_upload': {
                    'type': 'boolean',
                    'order': 16,
                    'description': 'Allow unauthenticated image uploads',
                    'default': False
                },
                'public_access_scrape': {
                    'type': 'boolean',
                    'order': 17,
                    'description': 'Allow unauthenticated web scrape jobs',
                    'default': False
                }
            }
        }
    }

    # Define Default configuration
    # Note: chat_deployed is always True since chat is deployed with SAM stack
    default_item = {
        'Configuration': 'Default',
        'chat_deployed': True,
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
        'chat_theme_overrides': {},
        'chat_allow_document_access': False,
        'public_access_chat': True,
        'public_access_search': True,
        'public_access_upload': False,
        'public_access_image_upload': False,
        'public_access_scrape': False
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
  python publish.py --project-name customer-docs --admin-email admin@example.com
  python publish.py --project-name legal-archive --admin-email admin@example.com --skip-ui
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
        default="us-east-1",
        help="AWS region (default: us-east-1). Nova Multimodal Embeddings currently requires us-east-1."
    )

    parser.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip UI build and deployment (still builds web component)"
    )

    parser.add_argument(
        "--skip-ui-all",
        action="store_true",
        help="Skip all UI builds (dashboard and web component)"
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

        # Check for us-east-1 requirement (Nova Multimodal Embeddings)
        if args.region != "us-east-1":
            log_warning(f"Region '{args.region}' selected, but Nova Multimodal Embeddings is currently only available in us-east-1.")
            log_warning("The Knowledge Base will fail to create unless the embedding model is available in your region.")
            response = input(f"{Colors.WARNING}Continue anyway? (y/N): {Colors.ENDC}").strip().lower()
            if response != 'y':
                log_info("Deployment cancelled. Use --region us-east-1 for Nova Multimodal Embeddings support.")
                sys.exit(0)

        log_success("All inputs validated")

        log_info(f"Project Name: {args.project_name}")
        log_info(f"Admin Email: {args.admin_email}")
        log_info(f"Region: {args.region}")

        # --skip-ui-all implies --skip-ui
        if args.skip_ui_all:
            args.skip_ui = True

        # Check prerequisites
        log_info("Checking prerequisites...")
        check_python_version()
        check_nodejs_version(skip_ui=args.skip_ui_all)
        check_aws_cli()
        check_sam_cli()
        # Docker check skipped for now
        # check_docker()
        log_success("All prerequisites met")

        # Create artifact bucket first
        try:
            artifact_bucket = create_sam_artifact_bucket(args.project_name, args.region)
        except OSError as e:
            log_error(f"Failed to create artifact bucket: {e}")
            sys.exit(1)

        # Package UI source (unless --skip-ui)
        ui_source_key = None
        if not args.skip_ui:
            try:
                ui_source_key = package_ui_source(artifact_bucket, args.region)
                log_info(f"UI source uploaded to {artifact_bucket}/{ui_source_key}")
            except (OSError, FileNotFoundError) as e:
                log_error(f"Failed to package UI: {e}")
                sys.exit(1)

        # Package web component source (unless --skip-ui-all)
        wc_source_key = None
        if not args.skip_ui_all:
            try:
                wc_source_key = package_ragstack_chat_source(artifact_bucket, args.region)
                log_info(f"Web component source uploaded to {artifact_bucket}/{wc_source_key}")
            except (OSError, FileNotFoundError) as e:
                log_error(f"Failed to package web component: {e}")
                sys.exit(1)

        # Note: Amplify placeholder is created automatically by CloudFormation custom resource
        # The CreateAmplifyPlaceholder resource creates a minimal valid zip in S3
        # Source will be overridden at build time via sourceLocationOverride

        # SAM build
        sam_build()

        # Check for failed stack and clean up if needed
        stack_name = f"RAGStack-{args.project_name}"
        try:
            handle_failed_stack(stack_name, args.region)
        except OSError as e:
            log_error(f"Failed to handle existing stack: {e}")
            sys.exit(1)

        # SAM deploy with UI and web component parameters
        stack_name = sam_deploy(
            args.project_name,
            args.admin_email,
            args.region,
            artifact_bucket,
            ui_source_key=ui_source_key,
            wc_source_key=wc_source_key,
            skip_ui=args.skip_ui
        )

        # Get outputs
        outputs = get_stack_outputs(stack_name, args.region)

        # Seed configuration table with CDN URL
        config_table_name = outputs.get('ConfigurationTableName')
        # Get CDN URL from stack outputs (set by CloudFormation)
        cdn_url = outputs.get('WebComponentCDNUrl', '')
        if config_table_name:
            # Check for existing chat CDN URL to preserve it (fallback to stack output)
            _, existing_chat_cdn = get_existing_chat_config(
                config_table_name, args.region
            )
            chat_cdn_url = existing_chat_cdn or cdn_url
            seed_configuration_table(stack_name, args.region, chat_cdn_url=chat_cdn_url)
        else:
            # Fallback if table name not in outputs
            seed_configuration_table(stack_name, args.region, chat_cdn_url=cdn_url)

        # Configure UI
        if not args.skip_ui:
            configure_ui(stack_name, args.region)

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
