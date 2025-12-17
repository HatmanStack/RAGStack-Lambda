"""
AppSync utilities for publishing real-time updates.

Lambdas use this to publish status updates via AppSync mutations,
which trigger subscriptions for connected clients.
"""

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger(__name__)

# Lazy-loaded session
_session = None


def _get_session():
    """Get or create boto3 session."""
    global _session
    if _session is None:
        _session = boto3.Session()
    return _session


def _sign_request(request, region):
    """Sign an AWS request using SigV4."""
    session = _get_session()
    credentials = session.get_credentials()
    frozen_credentials = credentials.get_frozen_credentials()

    sigv4 = SigV4Auth(frozen_credentials, "appsync", region)
    sigv4.add_auth(request)


def execute_appsync_mutation(graphql_endpoint: str, mutation: str, variables: dict) -> dict:
    """
    Execute a GraphQL mutation against AppSync using IAM auth.

    Args:
        graphql_endpoint: AppSync GraphQL endpoint URL
        mutation: GraphQL mutation string
        variables: Variables for the mutation

    Returns:
        GraphQL response data
    """
    region = os.environ.get("AWS_REGION", "us-east-1")

    payload = json.dumps({"query": mutation, "variables": variables}).encode("utf-8")

    # Create and sign the request
    request = AWSRequest(
        method="POST",
        url=graphql_endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
    )
    _sign_request(request, region)

    # Execute the request
    req = urllib.request.Request(
        graphql_endpoint, data=payload, headers=dict(request.headers), method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "errors" in result:
                logger.warning(f"GraphQL errors: {result['errors']}")
            return result
    except Exception as e:
        logger.error(f"Failed to execute AppSync mutation: {e}")
        raise


def publish_document_update(
    graphql_endpoint: str,
    document_id: str,
    filename: str,
    status: str,
    total_pages: int = None,
    error_message: str = None,
) -> None:
    """
    Publish a document status update to AppSync subscribers.

    Args:
        graphql_endpoint: AppSync GraphQL endpoint URL
        document_id: Document ID
        filename: Document filename
        status: New status (uppercase, e.g., "PROCESSING", "INDEXED")
        total_pages: Total pages (optional)
        error_message: Error message if failed (optional)
    """
    if not graphql_endpoint:
        logger.debug("No GraphQL endpoint configured, skipping subscription publish")
        return

    mutation = """
    mutation PublishDocumentUpdate(
        $documentId: ID!
        $filename: String!
        $status: DocumentStatus!
        $totalPages: Int
        $errorMessage: String
        $updatedAt: String!
    ) {
        publishDocumentUpdate(
            documentId: $documentId
            filename: $filename
            status: $status
            totalPages: $totalPages
            errorMessage: $errorMessage
            updatedAt: $updatedAt
        ) {
            documentId
            status
        }
    }
    """

    variables = {
        "documentId": document_id,
        "filename": filename,
        "status": status.upper(),
        "totalPages": total_pages,
        "errorMessage": error_message,
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    try:
        execute_appsync_mutation(graphql_endpoint, mutation, variables)
        logger.info(f"Published document update: {document_id} -> {status}")
    except Exception as e:
        # Don't fail the Lambda if subscription publish fails
        logger.warning(f"Failed to publish document update: {e}")


def publish_scrape_update(
    graphql_endpoint: str,
    job_id: str,
    base_url: str,
    title: str,
    status: str,
    total_urls: int,
    processed_count: int,
    failed_count: int,
) -> None:
    """
    Publish a scrape job status update to AppSync subscribers.

    Args:
        graphql_endpoint: AppSync GraphQL endpoint URL
        job_id: Scrape job ID
        base_url: Base URL being scraped
        title: Job title
        status: New status (uppercase)
        total_urls: Total discovered URLs
        processed_count: Successfully processed count
        failed_count: Failed count
    """
    if not graphql_endpoint:
        logger.debug("No GraphQL endpoint configured, skipping subscription publish")
        return

    mutation = """
    mutation PublishScrapeUpdate(
        $jobId: ID!
        $baseUrl: String!
        $title: String
        $status: ScrapeStatus!
        $totalUrls: Int!
        $processedCount: Int!
        $failedCount: Int!
        $updatedAt: String!
    ) {
        publishScrapeUpdate(
            jobId: $jobId
            baseUrl: $baseUrl
            title: $title
            status: $status
            totalUrls: $totalUrls
            processedCount: $processedCount
            failedCount: $failedCount
            updatedAt: $updatedAt
        ) {
            jobId
            status
        }
    }
    """

    variables = {
        "jobId": job_id,
        "baseUrl": base_url,
        "title": title,
        "status": status.upper(),
        "totalUrls": total_urls,
        "processedCount": processed_count,
        "failedCount": failed_count,
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    try:
        execute_appsync_mutation(graphql_endpoint, mutation, variables)
        logger.info(f"Published scrape update: {job_id} -> {status}")
    except Exception as e:
        # Don't fail the Lambda if subscription publish fails
        logger.warning(f"Failed to publish scrape update: {e}")


def publish_image_update(
    graphql_endpoint: str,
    image_id: str,
    filename: str,
    status: str,
    caption: str = None,
    error_message: str = None,
) -> None:
    """
    Publish an image status update to AppSync subscribers.

    Args:
        graphql_endpoint: AppSync GraphQL endpoint URL
        image_id: Image ID
        filename: Image filename
        status: New status (uppercase, e.g., "PROCESSING", "INDEXED", "FAILED")
        caption: Image caption (optional)
        error_message: Error message if failed (optional)
    """
    if not graphql_endpoint:
        logger.debug("No GraphQL endpoint configured, skipping subscription publish")
        return

    mutation = """
    mutation PublishImageUpdate(
        $imageId: ID!
        $filename: String!
        $status: ImageStatus!
        $caption: String
        $errorMessage: String
        $updatedAt: String!
    ) {
        publishImageUpdate(
            imageId: $imageId
            filename: $filename
            status: $status
            caption: $caption
            errorMessage: $errorMessage
            updatedAt: $updatedAt
        ) {
            imageId
            status
        }
    }
    """

    variables = {
        "imageId": image_id,
        "filename": filename,
        "status": status.upper(),
        "caption": caption,
        "errorMessage": error_message,
        "updatedAt": datetime.now(UTC).isoformat(),
    }

    try:
        execute_appsync_mutation(graphql_endpoint, mutation, variables)
        logger.info(f"Published image update: {image_id} -> {status}")
    except Exception as e:
        # Don't fail the Lambda if subscription publish fails
        logger.warning(f"Failed to publish image update: {e}")
