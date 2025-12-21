"""RAGStack MCP Server - Knowledge base tools for AI assistants."""

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
    Search the RAGStack knowledge base for relevant documents.

    Args:
        query: The search query (e.g., "authentication best practices", "API rate limits")
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
    Get a presigned URL to upload a document to the knowledge base.

    Supported file types: PDF, TXT, MD, HTML, DOC, DOCX, CSV, JSON, XML

    Args:
        filename: Name of the file to upload with extension (e.g., "report.pdf", "notes.md").
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


def main():
    """Run the MCP server."""
    if not GRAPHQL_ENDPOINT:
        print("Warning: RAGSTACK_GRAPHQL_ENDPOINT not set", file=sys.stderr, flush=True)
    if not API_KEY:
        print("Warning: RAGSTACK_API_KEY not set", file=sys.stderr, flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
