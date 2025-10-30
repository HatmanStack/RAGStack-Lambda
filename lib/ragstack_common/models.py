"""
Core data models for RAGStack-Lambda.

These models represent documents as they flow through the pipeline:
upload -> OCR -> embedding -> knowledge base
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class Status(str, Enum):
    """Processing status for documents."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    OCR_COMPLETE = "ocr_complete"
    EMBEDDING_COMPLETE = "embedding_complete"
    INDEXED = "indexed"
    FAILED = "failed"


class OcrBackend(str, Enum):
    """Supported OCR backends."""

    TEXTRACT = "textract"
    BEDROCK = "bedrock"
    TEXT_EXTRACTION = "text_extraction"


@dataclass
class Page:
    """
    Represents a single page from a document.

    Attributes:
        page_number: 1-indexed page number
        text: Extracted text content (from OCR or native extraction)
        image_s3_uri: S3 URI to page image (if applicable)
        ocr_backend: Which backend was used (textract/bedrock/none)
        confidence: Average OCR confidence score (0-100, if available)
    """

    page_number: int
    text: str = ""
    image_s3_uri: str | None = None
    ocr_backend: str | None = None
    confidence: float | None = None


@dataclass
class Document:
    """
    Main document container tracking state through the pipeline.

    Attributes:
        document_id: Unique identifier (typically S3 object key)
        filename: Original filename
        input_s3_uri: S3 location of uploaded file
        output_s3_uri: S3 location of extracted text/images
        status: Current processing status
        file_type: Document format (pdf, jpg, docx, etc.)
        is_text_native: True if PDF has embedded text
        pages: List of processed pages
        total_pages: Total number of pages
        error_message: Error details if status=FAILED
        created_at: Upload timestamp
        updated_at: Last update timestamp
        metadata: Additional metadata (file size, etc.)
    """

    document_id: str
    filename: str
    input_s3_uri: str
    status: Status = Status.UPLOADED
    file_type: str | None = None
    is_text_native: bool = False
    pages: list[Page] = field(default_factory=list)
    total_pages: int = 0
    output_s3_uri: str | None = None
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB storage."""
        data = {
            "document_id": self.document_id,
            "filename": self.filename,
            "input_s3_uri": self.input_s3_uri,
            "status": self.status.value,
            "is_text_native": self.is_text_native,
            "total_pages": self.total_pages,
        }

        # Add optional fields only if they have values
        if self.output_s3_uri:
            data["output_s3_uri"] = self.output_s3_uri
        if self.file_type:
            data["file_type"] = self.file_type
        if self.error_message:
            data["error_message"] = self.error_message
        if self.created_at:
            data["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            data["updated_at"] = self.updated_at.isoformat()
        if self.metadata:
            data["metadata"] = self.metadata

        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Create Document from DynamoDB record."""
        return cls(
            document_id=data["document_id"],
            filename=data["filename"],
            input_s3_uri=data["input_s3_uri"],
            output_s3_uri=data.get("output_s3_uri"),
            status=Status(data.get("status", "uploaded")),
            file_type=data.get("file_type"),
            is_text_native=data.get("is_text_native", False),
            total_pages=data.get("total_pages", 0),
            error_message=data.get("error_message"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class MeteringRecord:
    """
    Tracks token usage and costs for a document.

    Attributes:
        document_id: Associated document
        service: AWS service (textract, bedrock)
        operation: Specific operation (ocr, embedding, etc.)
        tokens_in: Input tokens (for Bedrock)
        tokens_out: Output tokens (for Bedrock)
        pages_processed: Number of pages (for Textract)
        timestamp: When operation occurred
        model_id: Bedrock model ID (if applicable)
    """

    document_id: str
    service: str
    operation: str
    tokens_in: int = 0
    tokens_out: int = 0
    pages_processed: int = 0
    timestamp: datetime | None = None
    model_id: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB storage."""
        data = {
            "document_id": self.document_id,
            "service": self.service,
            "operation": self.operation,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "pages_processed": self.pages_processed,
        }

        # Add optional fields only if they have values
        if self.timestamp:
            data["timestamp"] = self.timestamp.isoformat()
        if self.model_id:
            data["model_id"] = self.model_id

        return data
