#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
RAGStack-Lambda Deployment Script

One-click deployment automation for RAGStack-Lambda stack.

Usage:
    python publish.py --env dev
    python publish.py --env prod --admin-email admin@example.com
    python publish.py --env dev --skip-ui --skip-layers
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

    if version_info.major < 3:
        log_error("Python 3.12+ is required")
        log_info("Current version: Python {}.{}.{}".format(
            version_info.major, version_info.minor, version_info.micro
        ))
        sys.exit(1)

    if version_info.major == 3 and version_info.minor < 12:
        log_error("Python 3.12+ is required")
        log_info("Current version: Python {}.{}.{}".format(
            version_info.major, version_info.minor, version_info.micro
        ))
        log_info("Please upgrade Python and try again")
        sys.exit(1)

    log_success("Found Python {}.{}.{}".format(
        version_info.major, version_info.minor, version_info.micro
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


def prompt_for_email(default=None):
    """Prompt user for admin email with validation."""
    while True:
        if default:
            prompt_msg = f"Enter admin email address [{default}]: "
        else:
            prompt_msg = "Enter admin email address: "

        email = input(prompt_msg).strip()

        if not email and default:
            email = default

        if not email:
            log_error("Email address is required")
            continue

        if validate_email(email):
            return email
        else:
            log_error("Invalid email format. Please enter a valid email address (e.g., admin@example.com)")


def get_samconfig_value(env, key):
    """Read value from samconfig.toml for given environment."""
    try:
        import tomli
    except ImportError:
        # Fallback to manual parsing if tomli not available
        return None

    samconfig_path = Path("samconfig.toml")
    if not samconfig_path.exists():
        return None

    with open(samconfig_path, "rb") as f:
        config = tomli.load(f)

    section = config.get(env, {})
    deploy_params = section.get("deploy", {}).get("parameters", {})

    # Parse parameter_overrides array
    param_overrides = deploy_params.get("parameter_overrides", [])
    for param in param_overrides:
        if param.startswith(f"{key}="):
            return param.split("=", 1)[1]

    return None


def build_lambda_layers():
    """Build Lambda layers for shared dependencies."""
    log_info("Building Lambda layers...")

    layer_dir = Path("layers/python")
    layer_dir.mkdir(parents=True, exist_ok=True)

    # Install shared dependencies to layer
    requirements_file = Path("lib/ragstack_common/requirements.txt")

    if requirements_file.exists():
        log_info("Installing shared dependencies to layer...")
        run_command([
            "pip", "install",
            "-r", str(requirements_file),
            "-t", str(layer_dir),
            "--upgrade"
        ])
        log_success("Lambda layer built successfully")
    else:
        log_warning(f"Requirements file not found: {requirements_file}")


def sam_build(skip_layers=False):
    """Build SAM application."""
    log_info("Building SAM application...")

    if not skip_layers:
        build_lambda_layers()

    run_command(["sam", "build", "--parallel", "--cached"])
    log_success("SAM build complete")


def sam_deploy(env, admin_email, region="us-east-1"):
    """Deploy SAM application."""
    log_info(f"Deploying to {env} environment in {region}...")

    # Determine stack name and project name from environment
    if env == "prod":
        stack_name = "RAGStack-prod"
        project_name = "RAGStack-prod"
    else:
        stack_name = "RAGStack-dev"
        project_name = "RAGStack-dev"

    cmd = [
        "sam", "deploy",
        "--config-env", env,
        "--region", region,
        "--parameter-overrides",
        f"AdminEmail={admin_email}",
        f"ProjectName={project_name}"
    ]

    run_command(cmd)
    log_success(f"Deployment to {env} complete")
    return stack_name


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


def print_outputs(outputs, env, region):
    """Print stack outputs in a nice format."""
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}Deployment Complete! ({env} environment){Colors.ENDC}")
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


def main():
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
        print(f"{Colors.HEADER}RAGStack-Lambda Deployment ({args.env}){Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

        # Get admin email (prompt if not provided)
        if args.admin_email:
            admin_email = args.admin_email
            if not validate_email(admin_email):
                log_error("Invalid email format provided")
                sys.exit(1)
        else:
            # Try to get from samconfig.toml
            default_email = get_samconfig_value(args.env, "AdminEmail")
            admin_email = prompt_for_email(default=default_email)

        log_info(f"Environment: {args.env}")
        log_info(f"Admin Email: {admin_email}")
        log_info(f"Region: {args.region}")

        # SAM build
        if not args.skip_build:
            sam_build(skip_layers=args.skip_layers)

        # SAM deploy
        stack_name = sam_deploy(args.env, admin_email, args.region)

        # Get outputs
        outputs = get_stack_outputs(stack_name, args.region)

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
        print_outputs(outputs, args.env, args.region)

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
