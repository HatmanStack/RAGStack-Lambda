"""API Key Rotation Lambda

This Lambda function handles automatic rotation of the AppSync API key
used for public theme configuration access.

Triggered by EventBridge on a schedule (default: 30 days before expiry).
Creates a new API key and deletes the old one.
"""

import logging
import os
import time

import boto3
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Initialize clients
appsync = boto3.client("appsync")


def lambda_handler(event, context):
    """
    Rotate the AppSync API key.

    Creates a new key with 365-day expiration, then deletes old keys.

    Environment variables:
        APPSYNC_API_ID: The AppSync API ID

    Returns:
        dict: Status and new key ID
    """
    api_id = os.environ.get("APPSYNC_API_ID")
    if not api_id:
        raise ValueError("APPSYNC_API_ID environment variable not set")

    logger.info(f"Starting API key rotation for AppSync API: {api_id}")

    try:
        # List existing API keys
        existing_keys = []
        paginator = appsync.get_paginator("list_api_keys")
        for page in paginator.paginate(apiId=api_id):
            existing_keys.extend(page.get("apiKeys", []))

        logger.info(f"Found {len(existing_keys)} existing API key(s)")

        # Create new API key with 365-day expiration
        # AppSync expects Unix timestamp
        new_expiry = int(time.time()) + (365 * 24 * 60 * 60)

        new_key_response = appsync.create_api_key(
            apiId=api_id,
            description="Public API key for theme configuration (auto-rotated)",
            expires=new_expiry,
        )

        new_key_id = new_key_response["apiKey"]["id"]
        logger.info(f"Created new API key: {new_key_id}, expires: {new_expiry}")

        # Delete old keys (keep only the new one)
        deleted_count = 0
        for key in existing_keys:
            old_key_id = key["id"]
            try:
                appsync.delete_api_key(apiId=api_id, id=old_key_id)
                logger.info(f"Deleted old API key: {old_key_id}")
                deleted_count += 1
            except ClientError as e:
                # Log but continue - key might already be deleted
                logger.warning(f"Failed to delete key {old_key_id}: {e}")

        logger.info(f"API key rotation complete. Deleted {deleted_count} old key(s)")

        return {
            "statusCode": 200,
            "body": {
                "message": "API key rotated successfully",
                "newKeyId": new_key_id,
                "deletedKeys": deleted_count,
            },
        }

    except ClientError:
        logger.exception("Failed to rotate API key")
        raise
