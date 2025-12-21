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
def list_images(limit: int = 50) -> str:
    """
    List images in the knowledge base.

    Args:
        limit: Maximum number of images to return (1-100, default: 50)

    Returns:
        Multiline string with:
        - "Found N images:" header with count
        - For each image: "[STATUS] filename (imageId)" with optional caption
        - Returns "No images found." if no images exist

    Example:
        list_images(limit=10)
    """
    gql = """
    query ListImages($limit: Int) {
        listImages(limit: $limit) {
            items {
                imageId
                filename
                caption
                status
                s3Uri
            }
            nextToken
        }
    }
    """
    result = _graphql_request(gql, {"limit": limit})

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("listImages")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No images found."

    items = data.get("items", [])
    if not items:
        return "No images found."

    output = [f"Found {len(items)} images:\n"]
    for img in items:
        status = img.get("status", "Unknown")
        filename = img.get("filename", "Unknown")
        image_id = img.get("imageId", "")
        caption = img.get("caption", "")
        line = f"  [{status}] {filename} ({image_id})"
        if caption:
            line += f"\n    Caption: {caption[:100]}{'...' if len(caption) > 100 else ''}"
        output.append(line)

    return "\n".join(output)


@mcp.tool()
def list_documents(limit: int = 50) -> str:
    """
    List documents in the knowledge base.

    Args:
        limit: Maximum number of documents to return (1-100, default: 50)

    Returns:
        Multiline string with:
        - "Found N documents:" header with count
        - For each document: "[STATUS] filename (documentId)" with page count if available
        - Returns "No documents found." if no documents exist

    Example:
        list_documents(limit=10)
    """
    gql = """
    query ListDocuments($limit: Int) {
        listDocuments(limit: $limit) {
            items {
                documentId
                filename
                status
                fileType
                totalPages
                inputS3Uri
            }
            nextToken
        }
    }
    """
    result = _graphql_request(gql, {"limit": limit})

    if "error" in result:
        return f"Error: {result['error']}"

    data = result.get("data", {}).get("listDocuments")
    if data is None:
        errors = result.get("errors", [])
        if errors:
            return f"GraphQL error: {errors[0].get('message', 'Unknown error')}"
        return "No documents found."

    items = data.get("items", [])
    if not items:
        return "No documents found."

    output = [f"Found {len(items)} documents:\n"]
    for doc in items:
        status = doc.get("status", "Unknown")
        filename = doc.get("filename", "Unknown")
        doc_id = doc.get("documentId", "")
        file_type = doc.get("fileType", "")
        pages = doc.get("totalPages")
        line = f"  [{status}] {filename} ({doc_id})"
        if file_type:
            line += f" [{file_type}]"
        if pages:
            line += f" - {pages} pages"
        output.append(line)

    return "\n".join(output)


def main():
    """Run the MCP server."""
    if not GRAPHQL_ENDPOINT:
        print("Warning: RAGSTACK_GRAPHQL_ENDPOINT not set", file=sys.stderr, flush=True)
    if not API_KEY:
        print("Warning: RAGSTACK_API_KEY not set", file=sys.stderr, flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
