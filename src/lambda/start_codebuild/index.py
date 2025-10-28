"""CodeBuild Starter Lambda Function for UI Deployment"""
import logging
import os
import json

import boto3
from crhelper import CfnResource

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv('LOG_LEVEL', 'INFO'))

# Initialize CloudFormation helper
helper = CfnResource(
    json_logging=True,
    log_level=os.getenv('LOG_LEVEL', 'INFO'),
)

# Initialize boto3 client
codebuild_client = boto3.client('codebuild')


@helper.create
@helper.update
def create_or_update(event, context):
    """
    Start CodeBuild project on Create or Update.

    CloudFormation will invoke this function and wait for response.
    """
    logger.info("Starting CodeBuild project...")

    # Validate input
    resource_properties = event.get('ResourceProperties', {})
    project_name = resource_properties.get('BuildProjectName')

    if not project_name:
        raise ValueError("BuildProjectName is required in ResourceProperties")

    try:
        response = codebuild_client.start_build(projectName=project_name)
        build_id = response['build']['id']

        # Get AWS region for console URL
        region = os.environ.get('AWS_REGION', 'us-east-1')
        console_url = f"https://{region}.console.aws.amazon.com/codesuite/codebuild/projects/{project_name}/build/{build_id.split(':')[-1]}"

        logger.info(f"Started build: {build_id}")
        logger.info(f"Console URL: {console_url}")

        # Store build_id in helper data for polling (use update pattern)
        helper.Data.update({'build_id': build_id})

    except Exception as e:
        logger.exception("Failed to start build")
        raise


@helper.poll_create
@helper.poll_update
def poll_create_or_update(event, context):
    """
    Poll CodeBuild project until complete.

    Returns:
        True: Build succeeded (CloudFormation proceeds)
        None: Build in progress (CloudFormation will poll again)
        Raises: Build failed (CloudFormation rolls back)
    """
    build_id = event['CrHelperData']['build_id']

    try:
        response = codebuild_client.batch_get_builds(ids=[build_id])

        if not response['builds']:
            raise RuntimeError(f"Build not found: {build_id}")

        build = response['builds'][0]
        build_status = build['buildStatus']

        logger.info(f"Build status: {build_status}")

        if build_status == 'SUCCEEDED':
            logger.info("Build succeeded")
            return True

        if build_status == 'IN_PROGRESS':
            logger.info("Build in progress, will poll again...")
            return None

        # Failed, stopped, or timed out
        raise RuntimeError(f"Build did not complete successfully. Status: {build_status}")

    except Exception as e:
        logger.exception("Build polling error")
        raise


@helper.delete
def delete(event, context):
    """
    Handle Delete events (no-op for CodeBuild).

    We don't need to do anything on stack deletion.
    """
    logger.info("Delete event - no action needed")


def lambda_handler(event, context):
    """Lambda handler entry point"""
    logger.info(f"Received event: {json.dumps(event)}")
    return helper(event, context)
