"""RAGStack MCP Server - Knowledge base tools for AI assistants.

Provides tools to search, chat, upload documents/media, and scrape websites
into a RAGStack knowledge base. Supports documents, images, video, and audio
files with automatic transcription and semantic search.
"""

import os
import json
import sys
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("ragstack-kb")

# Configuration from environment
GRAPHQL_ENDPOINT = os.environ.get("RAGSTACK_GRAPHQL_ENDPOINT", "")
API_KEY = os.environ.get("RAGSTACK_API_KEY", "")


def _graphql_request(query: str, variables: dict | None = None) -> dict:
    """Execute a GraphQL request against the RAGStack API."""
    if not GRAPHQL_ENDPOINT:
        return {"error": "RAGSTACK_GRAPHQL_ENDPOINT not configured"}
    if not API_KEY:
        return {"error": "RAGSTACK_API_KEY not configured"}

    headers = {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(GRAPHQL_ENDPOINT, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        return {"error": f"HTTP error: {e}"}
    except Exception as e:
        return {"error": f"Request failed: {e}"}


@mcp.tool()
def search_knowledge_base(query: str, max_results: int = 5) -> str:
    """
    Search the RAGStack knowledge base for relevant documents and media.

    Searches across all indexed content including documents, images, and
    video/audio transcripts. For media files, results include timestamp
    information for the matching segment.

    Args:
        query: The search query (e.g., "authentication best practices", "what was discussed in the meeting")
        max_results: Maximum number of results to return (1-100, default: 5)

    Returns:
        Multiline string with search results:
        - "Found N results:" header
        - For each result: "[index] (score: X.XX) source_path" followed by content snippet
        - Content snippets are truncated to 500 characters
        - Returns "No results found." if no matches

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "Search error: <message>" - Backend search failure

    Example:
        search_knowledge_base("how to authenticate users", max_results=3)
    """
    gql = """
    query SearchKnowledgeBase($query: String!, $maxResults: Int) {
        searchKnowledgeBase(query: $query, maxResults: $maxResults) {
            query
            total
            error
            results {
                content
                source
                score
            }
        }
    }
    """
    result = _graphql_request(gql, {"query": query, "maxResults": max_results})

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("searchKnowledgeBase")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No results found."

    if data.get("error"):
        return f"Search error: {data['error']}"

    results = data.get("results", [])
    if not results:
        return "No results found."

    output = [f"Found {data.get('total', len(results))} results:\n"]
    for i, r in enumerate(results, 1):
        source = r.get("source", "Unknown")
        content = r.get("content", "")[:500]  # Truncate long content
        score = r.get("score", 0)
        output.append(f"[{i}] (score: {score:.2f}) {source}\n{content}\n")

    return "\n".join(output)


@mcp.tool()
def chat_with_knowledge_base(query: str, conversation_id: str | None = None) -> str:
    """
    Ask a question and get an AI-generated answer with source citations.

    Args:
        query: Your question in natural language (e.g., "What are the API rate limits?")
        conversation_id: Optional ID to maintain conversation context across multiple queries.
            Pass the conversation_id from a previous response to continue the conversation.

    Returns:
        Multiline string with:
        - AI-generated answer text
        - "Sources:" section listing cited documents with titles and URLs
          (for video/audio sources, includes timestamps like "1:30-2:00")
        - "[Conversation ID: xxx]" footer for continuing the conversation
        - Returns "No answer generated." if the AI couldn't generate a response

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "Error: HTTP error: <details>" - Network or API failure

    Example:
        # First question
        chat_with_knowledge_base("What authentication methods are supported?")

        # Follow-up question using conversation context
        chat_with_knowledge_base("How do I implement OAuth?", conversation_id="abc-123")
    """
    gql = """
    query QueryKnowledgeBase($query: String!, $conversationId: String) {
        queryKnowledgeBase(query: $query, conversationId: $conversationId) {
            answer
            conversationId
            error
            sources {
                documentId
                s3Uri
                snippet
                documentUrl
            }
        }
    }
    """
    variables = {"query": query}
    if conversation_id:
        variables["conversationId"] = conversation_id

    result = _graphql_request(gql, variables)

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("queryKnowledgeBase")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No answer generated."

    if data.get("error"):
        return f"Query error: {data['error']}"

    answer = data.get("answer", "No answer generated.")
    sources = data.get("sources", [])
    conv_id = data.get("conversationId", "")

    output = [answer, ""]
    if sources:
        output.append("Sources:")
        for s in sources:
            doc_id = s.get("documentId", "Unknown")
            url = s.get("documentUrl") or s.get("s3Uri", "")
            snippet = s.get("snippet", "")
            output.append(f"  - {doc_id}" + (f" ({url})" if url else ""))
            if snippet:
                output.append(f"    \"{snippet[:200]}...\"" if len(snippet) > 200 else f"    \"{snippet}\"")

    if conv_id:
        output.append(f"\n[Conversation ID: {conv_id}]")

    return "\n".join(output)


@mcp.tool()
def start_scrape_job(
    url: str,
    max_pages: int = 50,
    max_depth: int = 3,
    scope: str = "HOSTNAME",
    include_patterns: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
    scrape_mode: str = "AUTO",
    cookies: str | None = None,
    force_rescrape: bool = False,
) -> str:
    """
    Start a web scraping job to add website content to the knowledge base.

    Args:
        url: The starting URL to scrape (e.g., "https://docs.example.com/guide")
        max_pages: Maximum pages to scrape (1-1000, default: 50)
        max_depth: Maximum link depth to follow from start URL (0-10, default: 3).
            0 = only the starting page, 1 = start page + direct links, etc.
        scope: How far to crawl from the starting URL:
            - "SUBPAGES" - Only URLs under the starting path (e.g., /docs/*)
            - "HOSTNAME" - All pages on the same subdomain (default)
            - "DOMAIN" - All subdomains of the domain
        include_patterns: Only scrape URLs matching these glob patterns.
            Example: ["/docs/*", "/api/*"] to only scrape docs and api sections.
        exclude_patterns: Skip URLs matching these glob patterns.
            Example: ["/blog/*", "*.pdf"] to skip blog posts and PDFs.
        scrape_mode: How to fetch page content:
            - "AUTO" - Try fast HTTP, fall back to browser for JavaScript sites (default)
            - "FAST" - HTTP only, faster but may miss JavaScript-rendered content
            - "FULL" - Uses headless browser, slower but handles SPAs and JS content
        cookies: Cookie string for authenticated sites.
            Format: "name1=value1; name2=value2" (e.g., "session=abc123; auth=xyz")
        force_rescrape: If True, re-scrape all pages even if content hasn't changed.
            Useful when you want to refresh all content (default: False).

    Returns:
        Multiline string with:
        - "Scrape job started!" confirmation
        - "Job ID: <uuid>" - Use this ID to check status
        - "URL: <starting_url>"
        - "Status: PENDING" (initial status)

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "GraphQL error: <message>" - Invalid input or server error
        - "Error: HTTP error: <details>" - Network failure

    Example:
        # Basic scrape
        start_scrape_job("https://docs.example.com")

        # Scrape only docs section, excluding blog
        start_scrape_job(
            url="https://example.com",
            max_pages=200,
            max_depth=5,
            scope="HOSTNAME",
            include_patterns=["/docs/*", "/api/*"],
            exclude_patterns=["/blog/*", "/changelog/*"]
        )

        # Scrape authenticated site
        start_scrape_job(
            url="https://internal.example.com/docs",
            cookies="session=abc123; csrf_token=xyz789",
            scrape_mode="FULL"
        )
    """
    gql = """
    mutation StartScrape($input: StartScrapeInput!) {
        startScrape(input: $input) {
            jobId
            baseUrl
            status
        }
    }
    """
    input_data = {
        "url": url,
        "maxPages": max_pages,
        "maxDepth": max_depth,
        "scope": scope,
        "scrapeMode": scrape_mode,
        "forceRescrape": force_rescrape,
    }
    if include_patterns:
        input_data["includePatterns"] = include_patterns
    if exclude_patterns:
        input_data["excludePatterns"] = exclude_patterns
    if cookies:
        input_data["cookies"] = cookies

    variables = {"input": input_data}
    result = _graphql_request(gql, variables)

    if "error" in result:
        return f"Error: {result['error']}"

    errors = result.get("errors")
    if errors:
        return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"

    data = result.get("data", {}).get("startScrape", {})
    job_id = data.get("jobId", "Unknown")
    status = data.get("status", "Unknown")

    return f"Scrape job started!\nJob ID: {job_id}\nURL: {url}\nStatus: {status}"


@mcp.tool()
def get_scrape_job_status(job_id: str) -> str:
    """
    Check the status of a scrape job.

    Args:
        job_id: The scrape job ID returned from start_scrape_job (UUID format)

    Returns:
        Multiline string with:
        - "Job: <job_id>"
        - "URL: <base_url>" - The starting URL
        - "Title: <page_title>" - Title of the starting page (or "N/A")
        - "Status: <status>" - One of: PENDING, DISCOVERING, PROCESSING, COMPLETED, FAILED, CANCELLED
        - "Progress: X/Y pages" - Processed count / total discovered
        - "Failed: N" - Number of failed pages
        - Returns "Job <id> not found." if job doesn't exist

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "Error: HTTP error: <details>" - Network failure

    Example:
        get_scrape_job_status("a1b2c3d4-e5f6-7890-abcd-ef1234567890")
    """
    gql = """
    query GetScrapeJob($jobId: ID!) {
        getScrapeJob(jobId: $jobId) {
            job {
                jobId
                baseUrl
                title
                status
                totalUrls
                processedCount
                failedCount
            }
        }
    }
    """
    result = _graphql_request(gql, {"jobId": job_id})

    if "error" in result:
        return f"Error: {result['error']}"

    job = result.get("data", {}).get("getScrapeJob", {}).get("job", {})
    if not job:
        return f"Job {job_id} not found."

    return (
        f"Job: {job.get('jobId')}\n"
        f"URL: {job.get('baseUrl')}\n"
        f"Title: {job.get('title', 'N/A')}\n"
        f"Status: {job.get('status')}\n"
        f"Progress: {job.get('processedCount', 0)}/{job.get('totalUrls', 0)} pages\n"
        f"Failed: {job.get('failedCount', 0)}"
    )


@mcp.tool()
def list_scrape_jobs(limit: int = 10) -> str:
    """
    List recent scrape jobs.

    Args:
        limit: Maximum number of jobs to return (1-100, default: 10)

    Returns:
        Multiline string with:
        - "Recent scrape jobs:" header
        - For each job: "[STATUS] title (X/Y pages) - job_id"
        - Status is one of: PENDING, DISCOVERING, PROCESSING, COMPLETED, FAILED, CANCELLED
        - Returns "No scrape jobs found." if no jobs exist

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "Error: HTTP error: <details>" - Network failure

    Example:
        list_scrape_jobs(limit=5)
    """
    gql = """
    query ListScrapeJobs($limit: Int) {
        listScrapeJobs(limit: $limit) {
            items {
                jobId
                baseUrl
                title
                status
                processedCount
                totalUrls
            }
        }
    }
    """
    result = _graphql_request(gql, {"limit": limit})

    if "error" in result:
        return f"Error: {result['error']}"

    items = result.get("data", {}).get("listScrapeJobs", {}).get("items", [])
    if not items:
        return "No scrape jobs found."

    output = ["Recent scrape jobs:\n"]
    for job in items:
        status = job.get("status", "Unknown")
        title = job.get("title") or job.get("baseUrl", "Unknown")
        progress = f"{job.get('processedCount', 0)}/{job.get('totalUrls', 0)}"
        output.append(f"  [{status}] {title} ({progress} pages) - {job.get('jobId')}")

    return "\n".join(output)


@mcp.tool()
def upload_document_url(filename: str) -> str:
    """
    Get a presigned URL to upload a document or media file to the knowledge base.

    Supported file types:
    - Documents: PDF, TXT, MD, HTML, DOC, DOCX, CSV, JSON, XML, EML, EPUB, XLSX
    - Images: JPG, PNG, GIF, WebP, AVIF, BMP, TIFF
    - Video: MP4, WebM (transcribed via AWS Transcribe)
    - Audio: MP3, WAV, M4A, OGG, FLAC (transcribed via AWS Transcribe)

    Video/audio files are automatically transcribed and segmented into 30-second
    chunks for semantic search. Sources include timestamps for playback.

    Args:
        filename: Name of the file to upload with extension (e.g., "report.pdf", "meeting.mp4").
            The filename is used to determine content type and for display in the knowledge base.

    Returns:
        Multiline string with:
        - "Upload URL generated!" confirmation
        - "Document ID: <uuid>" - Unique ID for tracking the document
        - "Upload URL: <presigned_s3_url>" - URL to POST the file to
        - "To upload, POST a multipart form with these fields:" - Required form fields
        - JSON object with form fields to include in the upload
        - "Then append your file as 'file' field."

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "GraphQL error: Invalid filename" - Unsupported file type or invalid characters
        - "GraphQL error: <message>" - Server error

    Example:
        # Get upload URL for a PDF
        upload_document_url("quarterly-report.pdf")

        # Get upload URL for markdown
        upload_document_url("api-documentation.md")

        # Get upload URL for video (will be transcribed)
        upload_document_url("team-meeting.mp4")

        # Get upload URL for audio (will be transcribed)
        upload_document_url("podcast-episode.mp3")

    Note:
        After getting the URL, use a tool like curl to upload:
        curl -X POST "<upload_url>" -F "key=<key>" -F "...other fields..." -F "file=@report.pdf"
    """
    gql = """
    mutation CreateUploadUrl($filename: String!) {
        createUploadUrl(filename: $filename) {
            uploadUrl
            documentId
            fields
        }
    }
    """
    result = _graphql_request(gql, {"filename": filename})

    if "error" in result:
        return f"Error: {result['error']}"

    errors = result.get("errors")
    if errors:
        return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"

    data = result.get("data", {}).get("createUploadUrl", {})
    upload_url = data.get("uploadUrl", "")
    doc_id = data.get("documentId", "")
    fields = data.get("fields", "{}")

    return (
        f"Upload URL generated!\n\n"
        f"Document ID: {doc_id}\n"
        f"Upload URL: {upload_url}\n\n"
        f"To upload, POST a multipart form with these fields:\n"
        f"{fields}\n\n"
        f"Then append your file as 'file' field."
    )


@mcp.tool()
def upload_image_url(filename: str) -> str:
    """
    Get a presigned URL to upload an image to the knowledge base.

    This is step 1 of the image upload workflow:
    1. Call upload_image_url() to get presigned URL and image ID
    2. Upload the file to S3 using the returned URL and fields
    3. Optionally call generate_image_caption() to get an AI-generated caption
    4. Call submit_image() to finalize the upload with captions

    Supported image types: JPEG, PNG, GIF, WebP, BMP, TIFF

    Args:
        filename: Name of the image file with extension (e.g., "photo.jpg", "diagram.png").
            The filename determines content type and is displayed in the knowledge base.

    Returns:
        Multiline string with:
        - "Image upload URL generated!" confirmation
        - "Image ID: <uuid>" - Unique ID for tracking (use in submit_image)
        - "S3 URI: <s3://...>" - S3 location (use in generate_image_caption)
        - "Upload URL: <presigned_url>" - URL to POST the file to
        - "Form fields:" - JSON object with required form fields
        - Upload instructions using curl

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "GraphQL error: Invalid filename" - Unsupported file type
        - "GraphQL error: <message>" - Server error

    Example:
        # Get upload URL for a JPEG image
        upload_image_url("family-photo.jpg")

        # Get upload URL for a PNG diagram
        upload_image_url("architecture-diagram.png")
    """
    gql = """
    mutation CreateImageUploadUrl($filename: String!) {
        createImageUploadUrl(filename: $filename) {
            uploadUrl
            imageId
            s3Uri
            fields
        }
    }
    """
    result = _graphql_request(gql, {"filename": filename})

    if "error" in result:
        return f"Error: {result['error']}"

    errors = result.get("errors")
    if errors:
        return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"

    data = result.get("data", {}).get("createImageUploadUrl")
    if data is None:
        return "Error: No response from server"

    upload_url = data.get("uploadUrl", "")
    image_id = data.get("imageId", "")
    s3_uri = data.get("s3Uri", "")
    fields = data.get("fields", "{}")

    return (
        f"Image upload URL generated!\n\n"
        f"Image ID: {image_id}\n"
        f"S3 URI: {s3_uri}\n"
        f"Upload URL: {upload_url}\n\n"
        f"Form fields:\n{fields}\n\n"
        f"To upload with curl:\n"
        f"  curl -X POST '{upload_url}' \\\n"
        f"    -F '<field1>=<value1>' \\\n"
        f"    -F '<field2>=<value2>' \\\n"
        f"    ... (include all fields above) \\\n"
        f"    -F 'file=@{filename}'\n\n"
        f"After upload, call:\n"
        f"  generate_image_caption('{s3_uri}') - to get AI caption\n"
        f"  submit_image('{image_id}', ...) - to finalize with captions"
    )


@mcp.tool()
def generate_image_caption(s3_uri: str) -> str:
    """
    Generate an AI caption for an uploaded image using a vision model.

    This is step 3 (optional) of the image upload workflow. Call this after
    uploading the image file to S3 but before calling submit_image().

    The vision model analyzes the image and generates a descriptive caption
    that will be used for semantic search in the knowledge base.

    Args:
        s3_uri: The S3 URI of the uploaded image (returned by upload_image_url).
            Format: "s3://bucket-name/path/to/image.jpg"

    Returns:
        Multiline string with:
        - "AI Caption generated!" confirmation
        - "Caption: <generated_caption>" - The AI-generated description
        - Instructions for next step (submit_image)

        If generation fails:
        - "Caption generation failed: <error_message>"

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "GraphQL error: Image not found" - S3 URI doesn't exist or not accessible
        - "GraphQL error: <message>" - Vision model or server error

    Example:
        # Generate caption for an uploaded image
        generate_image_caption("s3://my-bucket/images/abc-123/photo.jpg")
    """
    gql = """
    mutation GenerateCaption($imageS3Uri: String!) {
        generateCaption(imageS3Uri: $imageS3Uri) {
            caption
            error
        }
    }
    """
    result = _graphql_request(gql, {"imageS3Uri": s3_uri})

    if "error" in result:
        return f"Error: {result['error']}"

    errors = result.get("errors")
    if errors:
        return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"

    data = result.get("data", {}).get("generateCaption")
    if data is None:
        return "Error: No response from server"

    if data.get("error"):
        return f"Caption generation failed: {data['error']}"

    caption = data.get("caption", "")
    if not caption:
        return "Caption generation failed: No caption returned"

    return (
        f"AI Caption generated!\n\n"
        f"Caption: {caption}\n\n"
        f"Use this caption in submit_image() as the 'ai_caption' parameter."
    )


@mcp.tool()
def submit_image(
    image_id: str,
    caption: str | None = None,
    user_caption: str | None = None,
    ai_caption: str | None = None,
) -> str:
    """
    Finalize an image upload and trigger indexing to the knowledge base.

    This is the final step of the image upload workflow. Call this after:
    1. Getting presigned URL with upload_image_url()
    2. Uploading the file to S3
    3. Optionally generating AI caption with generate_image_caption()

    The image will be indexed into the knowledge base using the provided captions
    for semantic search. At least one caption (caption, user_caption, or ai_caption)
    should be provided for meaningful search results.

    Args:
        image_id: The image ID returned by upload_image_url() (UUID format).
        caption: Primary caption for the image. If not provided, uses user_caption
            or ai_caption as fallback.
        user_caption: User-provided caption describing the image content.
            Use this for human-written descriptions.
        ai_caption: AI-generated caption from generate_image_caption().
            Use this for automatically generated descriptions.

    Returns:
        Multiline string with:
        - "Image submitted successfully!" confirmation
        - "Image ID: <uuid>"
        - "Filename: <original_filename>"
        - "Status: <PENDING|PROCESSING|INDEXED|FAILED>"
        - "Caption: <final_caption>" - The caption that will be indexed

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured" - Missing endpoint env var
        - "Error: RAGSTACK_API_KEY not configured" - Missing API key env var
        - "GraphQL error: Image not found" - Invalid image_id or image not uploaded
        - "GraphQL error: <message>" - Server error

    Example:
        # Submit with user-provided caption only
        submit_image("abc-123-uuid", user_caption="Family photo from 1985")

        # Submit with AI-generated caption
        submit_image("abc-123-uuid", ai_caption="A group of people standing outdoors")

        # Submit with both user and AI captions
        submit_image(
            "abc-123-uuid",
            user_caption="Grandpa's 80th birthday party",
            ai_caption="A group of people gathered around a birthday cake"
        )
    """
    gql = """
    mutation SubmitImage($input: SubmitImageInput!) {
        submitImage(input: $input) {
            imageId
            filename
            status
            caption
            userCaption
            aiCaption
            errorMessage
        }
    }
    """
    input_data = {"imageId": image_id}
    if caption:
        input_data["caption"] = caption
    if user_caption:
        input_data["userCaption"] = user_caption
    if ai_caption:
        input_data["aiCaption"] = ai_caption

    result = _graphql_request(gql, {"input": input_data})

    if "error" in result:
        return f"Error: {result['error']}"

    errors = result.get("errors")
    if errors:
        return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"

    data = result.get("data", {}).get("submitImage")
    if data is None:
        return "Error: No response from server"

    if data.get("errorMessage"):
        return f"Submit failed: {data['errorMessage']}"

    final_caption = data.get("caption") or data.get("userCaption") or data.get("aiCaption") or "None"

    return (
        f"Image submitted successfully!\n\n"
        f"Image ID: {data.get('imageId')}\n"
        f"Filename: {data.get('filename')}\n"
        f"Status: {data.get('status')}\n"
        f"Caption: {final_caption}\n\n"
        f"The image is now being processed and will be indexed to the knowledge base."
    )


# =============================================================================
# Configuration Tools (Read-Only)
# =============================================================================
# View current system configuration. Write access requires admin (Cognito) auth.
# =============================================================================


@mcp.tool()
def get_configuration() -> str:
    """
    Get the current RAGStack configuration settings (read-only).

    Returns all configuration values including chat settings, metadata extraction
    options, query-time filtering, public access controls, and more. This is
    read-only - configuration changes require admin access via the dashboard.

    Configuration Categories:

    **Chat Settings:**
    - chat_system_prompt: System prompt controlling AI behavior
    - chat_primary_model: Primary model for chat (e.g., claude-haiku-4-5)
    - chat_fallback_model: Fallback when quota exceeded (e.g., nova-micro)
    - chat_global_quota_daily: Total queries/day for all users
    - chat_per_user_quota_daily: Queries/day per authenticated user
    - chat_allow_document_access: Whether source document links are shown

    **Metadata Extraction (during document ingestion):**
    - metadata_extraction_enabled: Whether LLM extracts metadata from documents
    - metadata_extraction_model: Model used for extraction
    - metadata_extraction_mode: "auto" (LLM decides keys) or "manual"
    - metadata_manual_keys: Keys to extract in manual mode
    - metadata_max_keys: Maximum keys per document

    **Query-Time Filtering:**
    - filter_generation_enabled: Whether queries trigger filter generation
    - filter_generation_model: Model for generating filters from queries
    - multislice_enabled: Parallel filtered + unfiltered queries
    - multislice_count: Number of parallel retrieval slices (2-4)
    - multislice_timeout_ms: Timeout per slice in milliseconds

    **Public Access Controls:**
    - public_access_chat: Allow unauthenticated chat queries
    - public_access_search: Allow unauthenticated search
    - public_access_upload: Allow unauthenticated document uploads
    - public_access_image_upload: Allow unauthenticated image uploads
    - public_access_scrape: Allow unauthenticated web scraping

    **Document Processing:**
    - ocr_backend: "textract" or "bedrock" for OCR
    - image_caption_prompt: Prompt for AI image captioning

    **Media Processing (Video/Audio):**
    - transcribe_language_code: Language for AWS Transcribe (e.g., "en-US")
    - speaker_diarization_enabled: Whether to identify speakers
    - media_segment_duration_seconds: Chunk size for transcripts (default: 30)

    Returns:
        Formatted configuration organized by category showing:
        - Setting name
        - Current value (from merged Default + Custom config)
        - Data type

        Example output:
        ```
        RAGStack Configuration (read-only)

        === Chat Settings ===
        chat_primary_model: us.anthropic.claude-haiku-4-5-20251001-v1:0
        chat_fallback_model: us.amazon.nova-lite-v1:0
        chat_global_quota_daily: 10000
        chat_per_user_quota_daily: 100
        chat_allow_document_access: false
        chat_system_prompt: You are a helpful assistant...

        === Metadata Extraction ===
        metadata_extraction_enabled: true
        metadata_extraction_mode: auto
        ...
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "Error: RAGSTACK_API_KEY not configured"
        - "GraphQL error: Unauthorized" - API key doesn't have access

    Note:
        To modify configuration, use the RAGStack admin dashboard (requires
        Cognito authentication). API key access is read-only for security.

    Related Tools:
        - get_metadata_stats(): See metadata key statistics
        - get_filter_examples(): See filter examples in use
    """
    gql = """
    query GetConfiguration {
        getConfiguration {
            Schema
            Default
            Custom
        }
    }
    """
    result = _graphql_request(gql)

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("getConfiguration")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "Configuration not available."

    # Parse JSON strings
    try:
        schema = json.loads(data.get("Schema", "{}"))
        default = json.loads(data.get("Default", "{}"))
        custom = json.loads(data.get("Custom", "{}"))
    except json.JSONDecodeError as e:
        return f"Error parsing configuration: {e}"

    # Merge default and custom
    merged = {**default, **custom}

    # Organize by category
    categories = {
        "Chat Settings": [
            "chat_primary_model", "chat_fallback_model", "chat_global_quota_daily",
            "chat_per_user_quota_daily", "chat_allow_document_access", "chat_system_prompt"
        ],
        "Metadata Extraction": [
            "metadata_extraction_enabled", "metadata_extraction_model",
            "metadata_extraction_mode", "metadata_manual_keys", "metadata_max_keys"
        ],
        "Query-Time Filtering": [
            "filter_generation_enabled", "filter_generation_model",
            "multislice_enabled", "multislice_count", "multislice_timeout_ms"
        ],
        "Public Access": [
            "public_access_chat", "public_access_search", "public_access_upload",
            "public_access_image_upload", "public_access_scrape"
        ],
        "Document Processing": [
            "ocr_backend", "bedrock_ocr_model_id", "image_caption_prompt"
        ],
        "Media Processing": [
            "transcribe_language_code", "speaker_diarization_enabled",
            "media_segment_duration_seconds"
        ],
        "Budget": [
            "budget_alert_enabled", "budget_alert_threshold"
        ],
    }

    output = ["RAGStack Configuration (read-only)\n"]

    for category, keys in categories.items():
        category_values = []
        for key in keys:
            if key in merged:
                value = merged[key]
                # Truncate long values
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                elif isinstance(value, list):
                    value = json.dumps(value)
                category_values.append(f"  {key}: {value}")

        if category_values:
            output.append(f"=== {category} ===")
            output.extend(category_values)
            output.append("")

    # Show any uncategorized settings
    categorized_keys = set()
    for keys in categories.values():
        categorized_keys.update(keys)

    other_keys = [k for k in merged.keys() if k not in categorized_keys]
    if other_keys:
        output.append("=== Other ===")
        for key in sorted(other_keys):
            value = merged[key]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            output.append(f"  {key}: {value}")

    return "\n".join(output)


# =============================================================================
# Metadata Analysis Tools
# =============================================================================
# These tools help understand and optimize metadata extraction and filtering
# in the knowledge base. Metadata enables filtered searches like "show me
# documents about genealogy from the 1900s".
# =============================================================================


@mcp.tool()
def get_metadata_stats() -> str:
    """
    Get statistics about metadata keys extracted from documents in the knowledge base.

    This tool shows what metadata fields have been extracted from your documents,
    how often each key appears, sample values, and data types. Use this to understand
    what filters are available for searching.

    Metadata is extracted during document ingestion using LLM analysis. Common keys
    include: topic, document_type, date_range, location, author, organization.

    Returns:
        Formatted statistics for each metadata key:
        - Key name and data type (string, number, boolean, list)
        - Occurrence count (how many documents have this key)
        - Sample values (up to 5 examples)
        - Status (active/deprecated)

        Example output:
        ```
        Metadata Key Statistics (5 keys, last analyzed: 2024-01-15 10:30:00)

        1. topic (string) - 142 documents
           Sample values: "genealogy", "immigration", "census records"
           Status: active

        2. date_range (string) - 89 documents
           Sample values: "1850-1900", "1900-1950", "1800s"
           Status: active
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "Error: RAGSTACK_API_KEY not configured"
        - "No metadata keys found" - Run analyze_metadata() first

    Use Cases:
        - Discover what filters are available for search queries
        - Check if metadata extraction is working properly
        - Identify gaps in metadata coverage
        - Understand the structure of your document collection

    Related Tools:
        - analyze_metadata(): Trigger metadata analysis to discover keys
        - get_filter_examples(): See example filter queries
        - get_key_library(): Get full key library for suggestions
    """
    gql = """
    query GetMetadataStats {
        getMetadataStats {
            keys {
                keyName
                dataType
                occurrenceCount
                sampleValues
                status
            }
            totalKeys
            lastAnalyzed
            error
        }
    }
    """
    result = _graphql_request(gql)

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("getMetadataStats")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No metadata stats available."

    if data.get("error"):
        return f"Error: {data['error']}"

    keys = data.get("keys", [])
    if not keys:
        return "No metadata keys found. Run analyze_metadata() to discover keys from your documents."

    total = data.get("totalKeys", len(keys))
    last_analyzed = data.get("lastAnalyzed", "Never")

    output = [f"Metadata Key Statistics ({total} keys, last analyzed: {last_analyzed})\n"]

    for i, key in enumerate(keys, 1):
        name = key.get("keyName", "Unknown")
        dtype = key.get("dataType", "string")
        count = key.get("occurrenceCount", 0)
        samples = key.get("sampleValues", [])
        status = key.get("status", "active")

        output.append(f"{i}. {name} ({dtype}) - {count} documents")
        if samples:
            sample_str = ", ".join(f'"{s}"' for s in samples[:5])
            output.append(f"   Sample values: {sample_str}")
        output.append(f"   Status: {status}\n")

    return "\n".join(output)


@mcp.tool()
def get_filter_examples() -> str:
    """
    Get AI-generated filter examples for metadata-based search queries.

    Filter examples show how to construct metadata filters for common search
    patterns. These examples are used as few-shot learning prompts when the
    system generates filters from natural language queries.

    Each example includes:
    - Name: Short identifier for the filter pattern
    - Description: What the filter does
    - Use Case: When to apply this filter
    - Filter JSON: The actual filter syntax (S3 Vectors compatible)

    Filter Syntax Reference:
        Basic operators: $eq, $ne, $gt, $gte, $lt, $lte, $in, $nin, $exists
        Logical operators: $and, $or

        Examples:
        - {"topic": {"$eq": "genealogy"}} - exact match
        - {"date_range": {"$in": ["1900-1950", "1850-1900"]}} - match any
        - {"$and": [{"topic": {"$eq": "census"}}, {"location": {"$eq": "Ohio"}}]} - combine

    Returns:
        Formatted list of filter examples with JSON syntax.

        Example output:
        ```
        Filter Examples (5 examples, last generated: 2024-01-15)

        1. Census Records Filter
           Description: Find census and population records
           Use Case: Searching for demographic data
           Filter: {"document_type": {"$eq": "census"}}

        2. Geographic Filter
           Description: Filter by location
           Use Case: Finding documents about specific places
           Filter: {"location": {"$in": ["Ohio", "Pennsylvania"]}}
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "No filter examples found" - Run analyze_metadata() first

    Use Cases:
        - Understand available filter patterns
        - Learn the filter syntax for your metadata keys
        - See what query patterns the system recognizes
        - Debug why certain queries aren't being filtered

    Related Tools:
        - analyze_metadata(): Generate filter examples from your data
        - get_metadata_stats(): See what keys are available for filtering
    """
    gql = """
    query GetFilterExamples {
        getFilterExamples {
            examples {
                name
                description
                useCase
                filter
            }
            totalExamples
            lastGenerated
            error
        }
    }
    """
    result = _graphql_request(gql)

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("getFilterExamples")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No filter examples available."

    if data.get("error"):
        return f"Error: {data['error']}"

    examples = data.get("examples", [])
    if not examples:
        return "No filter examples found. Run analyze_metadata() to generate examples from your documents."

    total = data.get("totalExamples", len(examples))
    last_gen = data.get("lastGenerated", "Never")

    output = [f"Filter Examples ({total} examples, last generated: {last_gen})\n"]

    for i, ex in enumerate(examples, 1):
        name = ex.get("name", "Unnamed")
        desc = ex.get("description", "No description")
        use_case = ex.get("useCase", "General")
        filter_json = ex.get("filter", "{}")

        # Parse and pretty-print the filter
        try:
            if isinstance(filter_json, str):
                filter_obj = json.loads(filter_json)
            else:
                filter_obj = filter_json
            filter_str = json.dumps(filter_obj, indent=2)
        except (json.JSONDecodeError, TypeError):
            filter_str = str(filter_json)

        output.append(f"{i}. {name}")
        output.append(f"   Description: {desc}")
        output.append(f"   Use Case: {use_case}")
        output.append(f"   Filter: {filter_str}\n")

    return "\n".join(output)


@mcp.tool()
def get_key_library() -> str:
    """
    Get the complete metadata key library with all discovered keys.

    The key library contains all metadata keys that have been extracted from
    documents across the knowledge base. This is the authoritative list of
    keys available for filtering and analysis.

    Unlike get_metadata_stats(), this returns the raw key library data
    optimized for programmatic use and key suggestions.

    Returns:
        Complete list of metadata keys with:
        - Key name (the field name used in filters)
        - Data type (string, number, boolean, list)
        - Occurrence count (document frequency)
        - Sample values (example values for reference)
        - Status (active or deprecated)

        Example output:
        ```
        Key Library (8 keys)

        topic (string, 142 occurrences, active)
          Samples: genealogy, immigration, census
        date_range (string, 89 occurrences, active)
          Samples: 1850-1900, 1900-1950
        document_type (string, 156 occurrences, active)
          Samples: letter, photograph, certificate
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "Key library is empty" - No documents have been processed with metadata extraction

    Use Cases:
        - Get all available filter keys for query construction
        - Check key naming conventions before adding new documents
        - Identify similar keys that might need consolidation
        - Build autocomplete/suggestions for filter UI

    Related Tools:
        - check_key_similarity(): Check if a new key duplicates existing ones
        - get_metadata_stats(): Get detailed statistics with last analyzed time
    """
    gql = """
    query GetKeyLibrary {
        getKeyLibrary {
            keyName
            dataType
            occurrenceCount
            sampleValues
            status
        }
    }
    """
    result = _graphql_request(gql)

    if "error" in result:
        return f"Error: {result['error']}"

    keys = result.get("data", {}).get("getKeyLibrary")
    if keys is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "Key library not available."

    if not keys:
        return "Key library is empty. Process documents with metadata extraction enabled to populate it."

    output = [f"Key Library ({len(keys)} keys)\n"]

    for key in keys:
        name = key.get("keyName", "Unknown")
        dtype = key.get("dataType", "string")
        count = key.get("occurrenceCount", 0)
        status = key.get("status", "active")
        samples = key.get("sampleValues", [])

        output.append(f"{name} ({dtype}, {count} occurrences, {status})")
        if samples:
            sample_str = ", ".join(samples[:5])
            output.append(f"  Samples: {sample_str}")

    return "\n".join(output)


@mcp.tool()
def check_key_similarity(key_name: str, threshold: float = 0.8) -> str:
    """
    Check if a proposed metadata key is similar to existing keys in the library.

    Use this before adding documents with new metadata keys to avoid creating
    duplicate or inconsistent keys. For example, "author" vs "Author" vs
    "document_author" might all represent the same concept.

    The similarity check uses fuzzy string matching to find keys that might
    be duplicates or variations of the proposed key.

    Args:
        key_name: The proposed new key name to check (e.g., "author", "doc_type")
        threshold: Similarity threshold from 0.0 to 1.0 (default: 0.8)
            - 1.0 = exact match only
            - 0.8 = high similarity (recommended)
            - 0.5 = moderate similarity (catches more variations)

    Returns:
        Similarity analysis showing:
        - Whether similar keys were found
        - List of similar keys with similarity scores
        - Recommendation on whether to use existing key or create new one

        Example output:
        ```
        Key Similarity Check for "author"

        Similar keys found:
          - "document_author" (similarity: 0.85, 42 occurrences)
          - "Author" (similarity: 0.92, 18 occurrences)

        Recommendation: Consider using "document_author" instead to maintain
        consistency. It has higher usage across documents.
        ```

        If no similar keys:
        ```
        Key Similarity Check for "photograph_date"

        No similar keys found (threshold: 0.8)

        The key "photograph_date" appears to be unique. Safe to use.
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "GraphQL error: Invalid threshold" - threshold must be 0.0-1.0

    Use Cases:
        - Validate new key names before bulk document ingestion
        - Identify key consolidation opportunities
        - Maintain consistent metadata schema across documents
        - Debug unexpected filter behavior due to key variations

    Related Tools:
        - get_key_library(): See all existing keys
        - analyze_metadata(): Re-analyze to update key statistics
    """
    gql = """
    query CheckKeySimilarity($keyName: String!, $threshold: Float) {
        checkKeySimilarity(keyName: $keyName, threshold: $threshold) {
            proposedKey
            similarKeys {
                keyName
                similarity
                occurrenceCount
            }
            hasSimilar
        }
    }
    """
    result = _graphql_request(gql, {"keyName": key_name, "threshold": threshold})

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("checkKeySimilarity")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "Similarity check failed."

    proposed = data.get("proposedKey", key_name)
    similar = data.get("similarKeys", [])
    has_similar = data.get("hasSimilar", False)

    output = [f'Key Similarity Check for "{proposed}"\n']

    if has_similar and similar:
        output.append("Similar keys found:")
        best_match = None
        best_count = 0
        for sk in similar:
            name = sk.get("keyName", "Unknown")
            sim = sk.get("similarity", 0)
            count = sk.get("occurrenceCount", 0)
            output.append(f'  - "{name}" (similarity: {sim:.2f}, {count} occurrences)')
            if count > best_count:
                best_count = count
                best_match = name

        output.append("")
        if best_match:
            output.append(
                f'Recommendation: Consider using "{best_match}" instead to maintain '
                f"consistency. It has higher usage across documents."
            )
    else:
        output.append(f"No similar keys found (threshold: {threshold})\n")
        output.append(f'The key "{proposed}" appears to be unique. Safe to use.')

    return "\n".join(output)


@mcp.tool()
def analyze_metadata() -> str:
    """
    Trigger metadata analysis to discover keys and generate filter examples.

    This operation samples documents from the knowledge base, analyzes their
    metadata fields, updates the key library statistics, and generates new
    filter examples for few-shot learning.

    IMPORTANT: This is a potentially long-running operation (1-2 minutes).
    It samples up to 1000 vectors from the knowledge base and uses LLM
    analysis to generate filter examples.

    What happens during analysis:
    1. Samples vectors from the Bedrock Knowledge Base
    2. Extracts and counts metadata field occurrences
    3. Updates the key library with current statistics
    4. Generates 5-8 filter examples based on discovered keys
    5. Stores results for use in query-time filter generation

    When to run this:
    - After ingesting a significant batch of new documents
    - When filter generation isn't matching expected patterns
    - To refresh statistics after changing metadata extraction settings
    - When you see "No metadata keys found" in other tools

    Returns:
        Analysis summary showing:
        - Number of vectors sampled
        - Number of metadata keys analyzed
        - Number of filter examples generated
        - Execution time

        Example output:
        ```
        Metadata Analysis Complete!

        Vectors sampled: 847
        Keys analyzed: 12
        Filter examples generated: 6
        Execution time: 45,230 ms

        Analysis stored successfully. Use get_metadata_stats() and
        get_filter_examples() to view results.
        ```

    Errors:
        - "Error: RAGSTACK_GRAPHQL_ENDPOINT not configured"
        - "Analysis failed: <reason>" - Backend processing error
        - "Error: HTTP error: timeout" - Analysis took too long (try again)

    Performance Notes:
        - Samples up to 1000 vectors (not all documents)
        - LLM calls add latency for example generation
        - Safe to run multiple times; results are replaced not appended
        - Does not modify documents; only updates analytics data

    Related Tools:
        - get_metadata_stats(): View key statistics after analysis
        - get_filter_examples(): View generated filter examples
        - get_key_library(): View complete key library
    """
    gql = """
    mutation AnalyzeMetadata {
        analyzeMetadata {
            success
            vectorsSampled
            keysAnalyzed
            examplesGenerated
            executionTimeMs
            error
        }
    }
    """
    result = _graphql_request(gql)

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("analyzeMetadata")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "Analysis failed: No response from server."

    if not data.get("success"):
        error_msg = data.get("error", "Unknown error")
        return f"Analysis failed: {error_msg}"

    vectors = data.get("vectorsSampled", 0)
    keys = data.get("keysAnalyzed", 0)
    examples = data.get("examplesGenerated", 0)
    time_ms = data.get("executionTimeMs", 0)

    return (
        f"Metadata Analysis Complete!\n\n"
        f"Vectors sampled: {vectors:,}\n"
        f"Keys analyzed: {keys}\n"
        f"Filter examples generated: {examples}\n"
        f"Execution time: {time_ms:,} ms\n\n"
        f"Analysis stored successfully. Use get_metadata_stats() and\n"
        f"get_filter_examples() to view results."
    )


def main():
    """Run the MCP server."""
    if not GRAPHQL_ENDPOINT:
        print("Warning: RAGSTACK_GRAPHQL_ENDPOINT not set", file=sys.stderr, flush=True)
    if not API_KEY:
        print("Warning: RAGSTACK_API_KEY not set", file=sys.stderr, flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
