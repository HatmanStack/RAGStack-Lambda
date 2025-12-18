"""
Constants used throughout the RAGStack application.

Centralizes magic numbers and configuration values to improve
maintainability and make tuning easier.
"""

# =============================================================================
# Query Limits
# =============================================================================

# Maximum length of a user query in characters
MAX_QUERY_LENGTH = 10000

# Length of content snippet shown in search results
SNIPPET_LENGTH = 200

# Maximum number of messages to retain in chat history
MESSAGE_LIMIT = 50

# Maximum number of results to return from knowledge base queries
MAX_SEARCH_RESULTS = 100
DEFAULT_SEARCH_RESULTS = 5


# =============================================================================
# Timeouts (in seconds)
# =============================================================================

# Presigned URL expiration time (1 hour)
PRESIGNED_URL_EXPIRY = 3600

# Lambda function timeout (15 minutes)
LAMBDA_TIMEOUT = 900

# Ingestion Lambda timeout (5 minutes)
INGEST_TIMEOUT = 300

# Query Lambda timeout (1 minute)
QUERY_TIMEOUT = 60


# =============================================================================
# DynamoDB Pagination
# =============================================================================

# Default page size for list operations
DEFAULT_PAGE_SIZE = 50

# Maximum page size for list operations
MAX_PAGE_SIZE = 100


# =============================================================================
# OCR Processing
# =============================================================================

# Minimum extractable characters per page for quality check
MIN_EXTRACTABLE_CHARS_PER_PAGE = 50

# Maximum image dimension for Bedrock vision models
MAX_IMAGE_DIMENSION = 2048


# =============================================================================
# Rate Limiting (defaults)
# =============================================================================

# Default daily quota for all users combined
DEFAULT_GLOBAL_QUOTA_DAILY = 10000

# Default daily quota per user
DEFAULT_PER_USER_QUOTA_DAILY = 100


# =============================================================================
# Image Upload Constants
# =============================================================================

# Maximum image file size (10 MB)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024

# Supported image MIME types mapped to file extensions
SUPPORTED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# Supported image file extensions
SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# =============================================================================
# Embedding Model Configuration
# =============================================================================
# Note: Embedding model is configured in the Knowledge Base (template.yaml).
# Currently using Nova Multimodal Embeddings with 1024 dimensions.
# Bedrock KB handles embedding generation - no direct model calls needed.
