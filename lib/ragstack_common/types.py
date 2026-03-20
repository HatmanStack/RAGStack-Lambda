"""Type definitions for cross-module contracts.

These TypedDicts define the shapes of data structures that flow between
ragstack_common modules and Lambda handlers. Internal helper dicts
remain as dict[str, Any].
"""

from typing import NotRequired, TypedDict


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


class ChatResponse(TypedDict):
    """Response from the query_kb Lambda handler.

    Returned by lambda_handler to AppSync. Contains the AI-generated answer,
    conversation tracking ID, source citations, and optional error message.
    """

    answer: str
    conversationId: str | None
    sources: list[SourceInfo]
    error: NotRequired[str | None]
    filterApplied: NotRequired[str]


class ConversationTurn(TypedDict):
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
