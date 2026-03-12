"""Type definitions for cross-module contracts.

These TypedDicts define the shapes of data structures that flow between
ragstack_common modules and Lambda handlers. Internal helper dicts
remain as dict[str, Any].
"""

from typing import Any, TypedDict


class SourceInfo(TypedDict, total=False):
    """A single source citation from KB retrieval.

    Extracted from Bedrock Knowledge Base retrieve responses and included
    in ChatResponse.sources. Fields are optional because not all source
    types have all fields (e.g., images lack pageNumber).
    """

    documentId: str
    pageNumber: int | None
    s3Uri: str
    snippet: str
    score: float | None
    sourceUrl: str | None
    contentType: str | None
    # Document access fields
    documentUrl: str | None
    documentAccessAllowed: bool
    filename: str | None
    # Scraped content fields
    isScraped: bool
    # Image-specific fields
    isImage: bool
    thumbnailUrl: str | None
    caption: str | None
    # Media-specific fields
    isMedia: bool | None
    isSegment: bool
    segmentUrl: str | None
    mediaType: str | None
    timestampStart: int | None
    timestampEnd: int | None
    timestampDisplay: str | None
    speaker: str | None
    segmentIndex: int | None


class ChatResponse(TypedDict, total=False):
    """Response from the query_kb Lambda handler.

    Returned by lambda_handler to AppSync. Contains the AI-generated answer,
    conversation tracking ID, source citations, and optional error message.
    """

    answer: str
    conversationId: str | None
    sources: list[SourceInfo]
    error: str | None
    filterApplied: str


class ConversationTurn(TypedDict, total=False):
    """A single turn in a conversation stored in DynamoDB.

    Stored in the conversation history table with TTL for automatic cleanup.
    The query and answer fields capture the user's question and AI response.
    """

    conversationId: str
    timestamp: str
    query: str
    answer: str
    sources: str  # JSON-serialized list of SourceInfo
    ttl: int


class DocumentTrackingItem(TypedDict, total=False):
    """Document tracking record in DynamoDB.

    Tracks document processing status through the Step Functions pipeline.
    Used by process_document, ingest_to_kb, and batch_processor handlers.
    """

    document_id: str
    s3_uri: str
    status: str
    file_type: str
    filename: str
    uploaded_at: str
    processed_at: str
    error: str | None
    page_count: int
    output_s3_prefix: str


class FilterConfig(TypedDict, total=False):
    """Configuration for KB metadata filtering.

    Passed from the handler to FilterGenerator and MultiSliceRetriever.
    Controls whether and how metadata filters are applied to KB queries.
    """

    enabled: bool
    model_id: str | None
    filtered_score_boost: float
    filter_examples: list[dict[str, Any]]


class KBRetrievalResult(TypedDict, total=False):
    """A single result from Bedrock Knowledge Base retrieval.

    Represents one chunk returned by the retrieve API, including
    the content text, location metadata, and relevance score.
    """

    content: str
    s3Uri: str
    score: float
    metadata: dict[str, Any]


class S3Location(TypedDict):
    """Parsed S3 location with bucket and key components.

    Returned by parse_s3_uri and used throughout the pipeline
    for S3 operations.
    """

    bucket: str
    key: str


class IngestionJobResponse(TypedDict, total=False):
    """Response from Bedrock KB ingestion job start.

    Returned by start_ingestion_with_retry and ingest_documents_with_retry.
    Contains the job metadata needed for status tracking.
    """

    ingestionJob: dict[str, Any]


class MetadataAttributes(TypedDict, total=False):
    """Metadata attributes stored alongside KB documents in S3.

    Written as .metadata.json files by write_metadata_to_s3.
    Used by Bedrock Knowledge Base for filtering during retrieval.
    """

    metadataAttributes: dict[str, Any]
