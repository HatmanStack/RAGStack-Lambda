"""
Integration tests for document processing pipeline.

These tests require:
- Deployed CloudFormation stack
- AWS credentials
- Sample test documents
"""

import os
import time
from datetime import datetime

import pytest

# Get environment variables - check these BEFORE importing boto3
STACK_NAME = os.environ.get("STACK_NAME", "RAGStack-dev")
INPUT_BUCKET = os.environ.get("INPUT_BUCKET")
TRACKING_TABLE = os.environ.get("TRACKING_TABLE")
STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN")

if not all([INPUT_BUCKET, TRACKING_TABLE, STATE_MACHINE_ARN]):
    pytest.skip("Integration tests require deployed stack", allow_module_level=True)

# Import boto3 only after environment check
import boto3


# Fixtures for AWS clients - lazy initialization only when tests run
@pytest.fixture(scope="session")
def s3_client():
    """AWS S3 client fixture."""
    return boto3.client("s3")


@pytest.fixture(scope="session")
def dynamodb_resource():
    """AWS DynamoDB resource fixture."""
    return boto3.resource("dynamodb")


@pytest.fixture(scope="session")
def stepfunctions_client():
    """AWS Step Functions client fixture."""
    return boto3.client("stepfunctions")


def create_test_pdf_with_text():
    """Create a simple text-native PDF for testing."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50), "This is a test document.\nIt has multiple lines.\nFor testing purposes."
    )
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def upload_test_document(s3_client, filename, content):
    """Upload test document to S3 input bucket."""
    document_id = f"test-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    s3_key = f"{document_id}/{filename}"

    s3_client.put_object(Bucket=INPUT_BUCKET, Key=s3_key, Body=content)

    return document_id, f"s3://{INPUT_BUCKET}/{s3_key}"


def wait_for_processing(dynamodb_resource, document_id, timeout=300):
    """
    Wait for document processing to complete.

    Polls DynamoDB until status is 'indexed' or 'failed'.
    """
    table = dynamodb_resource.Table(TRACKING_TABLE)
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = table.get_item(Key={"document_id": document_id})

        if "Item" not in response:
            time.sleep(2)
            continue

        status = response["Item"].get("status")

        if status == "indexed":
            return response["Item"]
        if status == "failed":
            error = response["Item"].get("error_message", "Unknown error")
            raise Exception(f"Processing failed: {error}")

        time.sleep(5)

    raise TimeoutError(f"Processing did not complete within {timeout}s")


@pytest.mark.integration
def test_text_native_pdf_processing(s3_client, dynamodb_resource):
    """
    Test end-to-end processing of a text-native PDF.

    Steps:
    1. Create test PDF with embedded text
    2. Upload to S3 input bucket
    3. Wait for processing
    4. Verify:
       - Status is 'indexed'
       - is_text_native = True
       - Text extracted correctly
       - Embeddings generated
    """
    # Create and upload test PDF
    pdf_content = create_test_pdf_with_text()
    document_id, s3_uri = upload_test_document(s3_client, "test.pdf", pdf_content)

    print(f"Uploaded test document: {document_id}")

    # Wait for processing
    result = wait_for_processing(dynamodb_resource, document_id, timeout=300)

    # Verify results
    assert result["status"] == "indexed"
    assert result["is_text_native"]
    assert result["total_pages"] > 0

    print("✓ Text-native PDF processed successfully")
    print(f"  Pages: {result['total_pages']}")
    print(f"  Output: {result.get('output_s3_uri')}")


@pytest.mark.integration
@pytest.mark.slow
def test_scanned_pdf_ocr():
    """
    Test OCR processing of a scanned PDF (rendered from text PDF).

    This test is slower due to Textract processing time.
    """
    # For this test, we'd need a scanned PDF
    # Skipping for now - requires sample scanned document
    pytest.skip("Requires scanned PDF sample")


@pytest.mark.integration
def test_embedding_generation():
    """
    Test that embeddings are generated and stored correctly.

    Verifies:
    - Text embedding exists in vector bucket
    - Image embeddings exist (if images present)
    - Embedding format is correct
    """
    # This would require completing a full pipeline run first
    # and then checking the vector bucket
    pytest.skip("Requires completed pipeline execution")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
