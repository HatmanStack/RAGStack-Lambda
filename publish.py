#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
RAGStack-Lambda Deployment Script

One-click deployment automation for RAGStack-Lambda stack.

Usage:
    python publish.py
    python publish.py --admin-email admin@example.com --project-name MyRAGStack
    python publish.py --region us-west-2
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

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


def validate_project_name(name):
    """Validate project name (alphanumeric, hyphens, underscores)."""
    pattern = r'^[a-zA-Z0-9-_]+$'
    return re.match(pattern, name) is not None and len(name) > 0 and len(name) <= 64


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


def prompt_for_project_name(default="RAGStack"):
    """Prompt user for project name with validation."""
    while True:
        prompt_msg = f"Enter project name [{default}]: "
        name = input(prompt_msg).strip()

        if not name:
            name = default

        if validate_project_name(name):
            return name
        else:
            log_error("Invalid project name. Use only letters, numbers, hyphens, and underscores (max 64 chars)")


def sam_build():
    """Build SAM application."""
    log_info("Building SAM application...")
    run_command(["sam", "build", "--parallel", "--cached"])
    log_success("SAM build complete")


def sam_deploy(region, admin_email, project_name):
    """Deploy SAM application."""
    log_info(f"Deploying to {region}...")

    # Stack name includes project name
    stack_name = f"{project_name}-prod"

    cmd = [
        "sam", "deploy",
        "--region", region,
        "--stack-name", stack_name,
        "--capabilities", "CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND",
        "--resolve-s3",
        "--parameter-overrides",
        f"AdminEmail={admin_email}",
        f"ProjectName={project_name}"
    ]

    run_command(cmd)
    log_success(f"Deployment to {region} complete")
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


def invalidate_cloudfront(distribution_id, region="us-east-1"):
    """Invalidate CloudFront cache."""
    log_info(f"Invalidating CloudFront cache for distribution {distribution_id}...")

    run_command([
        "aws", "cloudfront", "create-invalidation",
        "--distribution-id", distribution_id,
        "--paths", "/*",
        "--region", region
    ])

    log_success("CloudFront cache invalidation initiated")


def print_outputs(outputs, region):
    """Print stack outputs in a nice format."""
    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
    print(f"{Colors.HEADER}Deployment Complete!{Colors.ENDC}")
    print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

    print(f"{Colors.BOLD}Stack Outputs:{Colors.ENDC}\n")

    for key, value in outputs.items():
        print(f"{Colors.BOLD}{key}:{Colors.ENDC} {value}")

    print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

    # Print UI URL if available
    if 'CloudFrontDomain' in outputs:
        ui_url = f"https://{outputs['CloudFrontDomain']}"
        print(f"{Colors.OKGREEN}UI URL:{Colors.ENDC} {ui_url}")
    elif 'UIBucketName' in outputs:
        # Fallback to S3 website URL if CloudFront not configured
        ui_url = f"http://{outputs['UIBucketName']}.s3-website-{region}.amazonaws.com"
        print(f"{Colors.WARNING}UI URL (S3 - no HTTPS):{Colors.ENDC} {ui_url}")

    if 'GraphQLApiUrl' in outputs:
        print(f"{Colors.OKGREEN}GraphQL API:{Colors.ENDC} {outputs['GraphQLApiUrl']}")

    if 'AdminEmail' in outputs or outputs.get('UserPoolId'):
        print(f"\n{Colors.OKGREEN}Next Steps:{Colors.ENDC}")
        print(f"1. Check your email for temporary password")
        print(f"2. Sign in to the UI and change your password")
        print(f"3. Upload a document to test the pipeline")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Deploy RAGStack-Lambda to AWS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python publish.py
  python publish.py --admin-email admin@example.com --project-name MyRAGStack
  python publish.py --region us-west-2 --skip-ui
        """
    )

    parser.add_argument(
        "--admin-email",
        help="Admin user email address"
    )

    parser.add_argument(
        "--project-name",
        default="RAGStack",
        help="Project name prefix for resources (default: RAGStack)"
    )

    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)"
    )

    parser.add_argument(
        "--skip-ui",
        action="store_true",
        help="Skip UI build and deployment"
    )

    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip SAM build (use existing build)"
    )

    args = parser.parse_args()

    try:
        print(f"\n{Colors.HEADER}{'=' * 60}{Colors.ENDC}")
        print(f"{Colors.HEADER}RAGStack-Lambda Deployment{Colors.ENDC}")
        print(f"{Colors.HEADER}{'=' * 60}{Colors.ENDC}\n")

        # Get admin email (prompt if not provided)
        if args.admin_email:
            admin_email = args.admin_email
            if not validate_email(admin_email):
                log_error("Invalid email format provided")
                sys.exit(1)
        else:
            admin_email = prompt_for_email()

        # Get project name (prompt if not provided or use default)
        if not args.project_name:
            project_name = prompt_for_project_name()
        else:
            project_name = args.project_name
            if not validate_project_name(project_name):
                log_error("Invalid project name provided")
                sys.exit(1)

        log_info(f"Admin Email: {admin_email}")
        log_info(f"Project Name: {project_name}")
        log_info(f"Region: {args.region}")

        # SAM build
        if not args.skip_build:
            sam_build()

        # SAM deploy
        stack_name = sam_deploy(args.region, admin_email, project_name)

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
                    invalidate_cloudfront(outputs['CloudFrontDistributionId'], args.region)

        # Print outputs
        print_outputs(outputs, args.region)

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
