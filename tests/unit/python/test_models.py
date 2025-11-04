from datetime import datetime

from ragstack_common.models import Document, Status


def test_document_creation():
    doc = Document(document_id="test-123", filename="test.pdf", input_s3_uri="s3://bucket/test.pdf")
    assert doc.status == Status.UPLOADED
    assert doc.pages == []
    print("✓ Document creation works")


def test_document_serialization():
    doc = Document(
        document_id="test-123",
        filename="test.pdf",
        input_s3_uri="s3://bucket/test.pdf",
        created_at=datetime.now(),
    )
    data = doc.to_dict()
    assert data["document_id"] == "test-123"
    assert data["status"] == "uploaded"

    doc2 = Document.from_dict(data)
    assert doc2.document_id == doc.document_id
    print("✓ Document serialization works")


if __name__ == "__main__":
    test_document_creation()
    test_document_serialization()
    print("All model tests passed!")
