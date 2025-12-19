"""RAGStack MCP Server - Knowledge base tools for AI assistants."""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP(
    "ragstack-kb",
    description="Search, chat, upload, and scrape your RAGStack knowledge base",
)

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
        query: The search query
        max_results: Maximum number of results to return (default: 5)

    Returns:
        Search results with content snippets and sources
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

    data = result.get("data", {}).get("searchKnowledgeBase", {})
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
        query: Your question
        conversation_id: Optional ID to maintain conversation context

    Returns:
        AI-generated answer with source citations
    """
    gql = """
    query QueryKnowledgeBase($query: String!, $conversationId: String) {
        queryKnowledgeBase(query: $query, conversationId: $conversationId) {
            answer
            conversationId
            sources {
                title
                snippet
                url
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

    data = result.get("data", {}).get("queryKnowledgeBase", {})
    answer = data.get("answer", "No answer generated.")
    sources = data.get("sources", [])
    conv_id = data.get("conversationId", "")

    output = [answer, ""]
    if sources:
        output.append("Sources:")
        for s in sources:
            title = s.get("title", "Unknown")
            url = s.get("url", "")
            output.append(f"  - {title}" + (f" ({url})" if url else ""))

    if conv_id:
        output.append(f"\n[Conversation ID: {conv_id}]")

    return "\n".join(output)


@mcp.tool()
def start_scrape_job(
    url: str,
    max_pages: int = 50,
    max_depth: int = 3,
    scope: str = "HOSTNAME",
) -> str:
    """
    Start a web scraping job to add website content to the knowledge base.

    Args:
        url: The URL to start scraping from
        max_pages: Maximum pages to scrape (default: 50)
        max_depth: Maximum link depth to follow (default: 3)
        scope: Scrape scope - SUBPAGES, HOSTNAME, or DOMAIN (default: HOSTNAME)

    Returns:
        Job ID and status
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
    variables = {
        "input": {
            "url": url,
            "maxPages": max_pages,
            "maxDepth": max_depth,
            "scope": scope,
        }
    }
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
        job_id: The scrape job ID

    Returns:
        Job status and progress
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
        limit: Maximum number of jobs to return (default: 10)

    Returns:
        List of scrape jobs with status
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

    Args:
        filename: Name of the file to upload (e.g., 'report.pdf')

    Returns:
        Upload URL and instructions
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


def main():
    """Run the MCP server."""
    if not GRAPHQL_ENDPOINT:
        print("Warning: RAGSTACK_GRAPHQL_ENDPOINT not set", flush=True)
    if not API_KEY:
        print("Warning: RAGSTACK_API_KEY not set", flush=True)
    mcp.run()


if __name__ == "__main__":
    main()
