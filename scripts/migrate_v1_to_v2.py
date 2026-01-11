#!/usr/bin/env python3
"""
Migration script for RAGStack v1.x to v2.0.

This script migrates deployed stacks from the dual data source architecture
(output/ and images/ prefixes) to the unified single data source (content/ prefix).

Steps performed:
1. Copy S3 files from output/ and images/ to content/
2. Update DynamoDB tracking table with new S3 URIs
3. Report migration statistics

After running this script:
1. Deploy the new v2.0 stack (sam deploy)
2. Trigger reindex from the Settings UI to regenerate vectors with new metadata

Usage:
    python scripts/migrate_v1_to_v2.py --stack-name <your-stack-name> [--dry-run]

Requirements:
    - AWS credentials configured
    - boto3 installed
    - Stack must be deployed and accessible
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class MigrationStats:
    """Track migration statistics."""

    documents_copied: int = 0
    images_copied: int = 0
    tracking_records_updated: int = 0
    errors: int = 0
    skipped: int = 0


def get_stack_outputs(stack_name: str, region: str) -> dict[str, str]:
    """Get CloudFormation stack outputs."""
    cfn = boto3.client("cloudformation", region_name=region)
    try:
        response = cfn.describe_stacks(StackName=stack_name)
        stacks = response.get("Stacks", [])
        if not stacks:
            raise ValueError(f"Stack not found: {stack_name}")

        outputs = {}
        for output in stacks[0].get("Outputs", []):
            outputs[output["OutputKey"]] = output["OutputValue"]
        return outputs
    except ClientError as e:
        logger.error(f"Failed to get stack outputs: {e}")
        raise


def copy_s3_prefix(
    s3_client: Any,
    bucket: str,
    source_prefix: str,
    dest_prefix: str,
    dry_run: bool = False,
) -> int:
    """
    Copy all objects from source prefix to destination prefix.

    Returns:
        Number of objects copied
    """
    copied = 0
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=bucket, Prefix=source_prefix):
        for obj in page.get("Contents", []):
            source_key = obj["Key"]

            # Calculate destination key by replacing prefix
            relative_path = source_key[len(source_prefix) :]
            dest_key = f"{dest_prefix}{relative_path}"

            if dry_run:
                logger.info(f"[DRY RUN] Would copy: {source_key} -> {dest_key}")
            else:
                try:
                    # Check if destination already exists
                    try:
                        s3_client.head_object(Bucket=bucket, Key=dest_key)
                        logger.debug(f"Skipping existing: {dest_key}")
                        continue
                    except ClientError as e:
                        if e.response["Error"]["Code"] != "404":
                            raise

                    # Copy object
                    s3_client.copy_object(
                        Bucket=bucket,
                        CopySource={"Bucket": bucket, "Key": source_key},
                        Key=dest_key,
                    )
                    logger.debug(f"Copied: {source_key} -> {dest_key}")
                except Exception as e:
                    logger.error(f"Failed to copy {source_key}: {e}")
                    continue

            copied += 1

    return copied


def update_tracking_record(
    table: Any,
    item: dict,
    bucket: str,
    dry_run: bool = False,
) -> str:
    """
    Update a tracking record with new content/ prefix paths.

    Returns:
        "updated" if record was updated
        "skipped" if no changes needed
        "failed" if update failed
    """
    doc_id = item.get("document_id")

    # Build update expression and values
    update_parts = []
    expr_values = {}

    # Update output_s3_uri (documents, images, scraped)
    output_uri = item.get("output_s3_uri", "")
    if output_uri and ("/output/" in output_uri or "/images/" in output_uri):
        new_output_uri = output_uri.replace("/output/", "/content/").replace(
            "/images/", "/content/"
        )
        update_parts.append("output_s3_uri = :output_uri")
        expr_values[":output_uri"] = new_output_uri

    # Update input_s3_uri for images (they reference images/ prefix)
    input_uri = item.get("input_s3_uri", "")
    if input_uri and "/images/" in input_uri:
        new_input_uri = input_uri.replace("/images/", "/content/")
        update_parts.append("input_s3_uri = :input_uri")
        expr_values[":input_uri"] = new_input_uri

    # Update caption_s3_uri for images
    caption_uri = item.get("caption_s3_uri", "")
    if caption_uri and "/images/" in caption_uri:
        new_caption_uri = caption_uri.replace("/images/", "/content/")
        update_parts.append("caption_s3_uri = :caption_uri")
        expr_values[":caption_uri"] = new_caption_uri

    if not update_parts:
        logger.debug(f"No updates needed for {doc_id}")
        return "skipped"

    update_expr = "SET " + ", ".join(update_parts)

    if dry_run:
        logger.info(f"[DRY RUN] Would update {doc_id}: {update_expr}")
        logger.info(f"  Values: {json.dumps(expr_values, indent=2)}")
        return "updated"

    try:
        table.update_item(
            Key={"document_id": doc_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
        logger.debug(f"Updated tracking record: {doc_id}")
        return "updated"
    except Exception as e:
        logger.error(f"Failed to update {doc_id}: {e}")
        return "failed"


def migrate_stack(
    stack_name: str,
    region: str = "us-east-1",
    dry_run: bool = False,
) -> MigrationStats:
    """
    Migrate a RAGStack v1.x deployment to v2.0.

    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        dry_run: If True, only log what would be done

    Returns:
        Migration statistics
    """
    stats = MigrationStats()

    prefix = "[DRY RUN] " if dry_run else ""
    logger.info(f"{prefix}Starting migration for stack: {stack_name}")

    # Get stack outputs
    outputs = get_stack_outputs(stack_name, region)
    bucket = outputs.get("DataBucketName")
    tracking_table_name = outputs.get("TrackingTableName")

    if not bucket:
        raise ValueError("DataBucketName not found in stack outputs")
    if not tracking_table_name:
        raise ValueError("TrackingTableName not found in stack outputs")

    logger.info(f"Data bucket: {bucket}")
    logger.info(f"Tracking table: {tracking_table_name}")

    # Initialize AWS clients
    s3 = boto3.client("s3", region_name=region)
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(tracking_table_name)

    # Step 1: Copy output/ -> content/
    logger.info("Step 1: Copying documents from output/ to content/...")
    stats.documents_copied = copy_s3_prefix(
        s3, bucket, "output/", "content/", dry_run=dry_run
    )
    logger.info(f"  Copied {stats.documents_copied} document files")

    # Step 2: Copy images/ -> content/
    logger.info("Step 2: Copying images from images/ to content/...")
    stats.images_copied = copy_s3_prefix(
        s3, bucket, "images/", "content/", dry_run=dry_run
    )
    logger.info(f"  Copied {stats.images_copied} image files")

    # Step 3: Update tracking table
    logger.info("Step 3: Updating tracking table records...")
    paginator_kwargs: dict = {}
    while True:
        response = table.scan(**paginator_kwargs)
        items = response.get("Items", [])

        for item in items:
            result = update_tracking_record(table, item, bucket, dry_run=dry_run)
            if result == "updated":
                stats.tracking_records_updated += 1
            elif result == "skipped":
                stats.skipped += 1
            else:  # "failed"
                stats.errors += 1

        if "LastEvaluatedKey" not in response:
            break
        paginator_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

    logger.info(f"  Updated {stats.tracking_records_updated} tracking records")
    logger.info(f"  Skipped {stats.skipped} records (already migrated or no changes)")
    if stats.errors:
        logger.warning(f"  Failed {stats.errors} records (see errors above)")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Migrate RAGStack v1.x to v2.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run (see what would be changed)
    python scripts/migrate_v1_to_v2.py --stack-name my-rag-stack --dry-run

    # Actual migration
    python scripts/migrate_v1_to_v2.py --stack-name my-rag-stack

    # With specific region
    python scripts/migrate_v1_to_v2.py --stack-name my-rag-stack --region us-west-2

After migration:
    1. Deploy the updated v2.0 stack:
       sam build && sam deploy --stack-name my-rag-stack

    2. Trigger reindex from Settings UI to regenerate vectors
""",
    )
    parser.add_argument(
        "--stack-name",
        required=True,
        help="CloudFormation stack name to migrate",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        stats = migrate_stack(
            stack_name=args.stack_name,
            region=args.region,
            dry_run=args.dry_run,
        )

        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print("=" * 60)
        print(f"Documents copied:        {stats.documents_copied}")
        print(f"Images copied:           {stats.images_copied}")
        print(f"Tracking records updated: {stats.tracking_records_updated}")
        print(f"Records skipped:         {stats.skipped}")
        print(f"Errors:                  {stats.errors}")
        print("=" * 60)

        if args.dry_run:
            print("\nThis was a DRY RUN. No changes were made.")
            print("Run without --dry-run to perform the actual migration.")
        else:
            print("\nMigration complete!")
            print("\nNext steps:")
            print("  1. Deploy the v2.0 stack: sam build && sam deploy")
            print("  2. Open the Settings UI and click 'Start Reindex'")
            print("  3. Wait for reindex to complete")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
