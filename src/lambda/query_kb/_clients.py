"""Shared AWS clients for query_kb package.

Module-level boto3 clients are initialized once and reused across
warm Lambda invocations. Imported by other modules in the package.
"""

import boto3

s3_client = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
dynamodb_client = boto3.client("dynamodb")
bedrock_agent = boto3.client("bedrock-agent-runtime")
bedrock_runtime = boto3.client("bedrock-runtime")
