"""CodeBuild Starter Lambda Function for UI Deployment"""

import json
import logging
import os
from urllib.parse import quote

import boto3
from crhelper import CfnResource

logger = logging.getLogger(__name__)
logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))

# Initialize CloudFormation helper
helper = CfnResource(
    json_logging=True,
    log_level=os.getenv("LOG_LEVEL", "INFO"),
)

# Initialize boto3 client
codebuild_client = boto3.client("codebuild")


def _redact_event(event):
    """
    Redact sensitive fields from CloudFormation event before logging.

    Args:
        event: CloudFormation event dict

    Returns:
        dict: Event with sensitive fields redacted
    """
    if not isinstance(event, dict):
        return "***non-dict***"

    redacted = event.copy()
    sensitive_fields = ["ResourceProperties", "ResponseURL", "ServiceToken"]

    for field in sensitive_fields:
        if field in redacted:
            redacted[field] = "***redacted***"

    return redacted


@helper.create
@helper.update
def create_or_update(event, context):
    """
    Start CodeBuild project on Create or Update.

    CloudFormation will invoke this function and wait for response.
    Supports optional SourceLocationOverride for SAR deployments where
    source is deployed to S3 by a custom resource.
    """
    logger.info("Starting CodeBuild project...")

    # Validate input
    resource_properties = event.get("ResourceProperties", {})
    project_name = resource_properties.get("BuildProjectName")
    source_location_override = resource_properties.get("SourceLocationOverride")

    if not project_name:
        raise ValueError("BuildProjectName is required in ResourceProperties")

    try:
        # Build parameters
        build_params = {
            "projectName": project_name,
            "idempotencyToken": event.get("RequestId"),  # Prevent duplicate builds on retries
        }

        # Add source location override for SAR deployments
        if source_location_override:
            logger.info(f"Using source location override: {source_location_override}")
            build_params["sourceLocationOverride"] = source_location_override

        response = codebuild_client.start_build(**build_params)
        build_id = response["build"]["id"]

        # Get AWS region for console URL (prefer client metadata)
        region = codebuild_client.meta.region_name or os.environ.get("AWS_REGION", "us-east-1")
        encoded_build_id = quote(build_id, safe="")
        console_url = (
            f"https://{region}.console.aws.amazon.com/codesuite/codebuild/"
            f"projects/{project_name}/build/{encoded_build_id}/?region={region}"
        )

        logger.info(f"Started build: {build_id}")
        logger.info(f"Console URL: {console_url}")

        # Store build_id and console URL in helper data for polling and CFN response
        helper.Data.update({"build_id": build_id, "ConsoleUrl": console_url})

    except Exception:
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
    # Defensive: validate CrHelperData exists before accessing
    build_id = event.get("CrHelperData", {}).get("build_id")
    if not build_id:
        raise ValueError("CrHelperData.build_id missing; ensure create handler stored it")

    try:
        response = codebuild_client.batch_get_builds(ids=[build_id])

        if not response["builds"]:
            not_found = response.get("buildsNotFound") or []
            raise RuntimeError(f"Build not found: {build_id}. NotFound: {not_found}")

        build = response["builds"][0]
        build_status = build["buildStatus"]

        logger.info(f"Build status: {build_status}")

        if build_status == "SUCCEEDED":
            logger.info("Build succeeded")
            return True

        if build_status == "IN_PROGRESS":
            logger.info("Build in progress, will poll again...")
            return None

        # Failed, stopped, or timed out
        raise RuntimeError(f"Build did not complete successfully. Status: {build_status}")

    except Exception:
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
    logger.info(f"Received event: {json.dumps(_redact_event(event))}")
    return helper(event, context)
