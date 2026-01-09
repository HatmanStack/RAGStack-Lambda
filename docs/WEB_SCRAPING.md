# Web Scraping

Scrape websites and index content into the knowledge base.

## Quick Start

1. **Dashboard → Scrape tab → Enter URL**
2. Configure scope and depth
3. Click "Start Scrape"
4. Content auto-indexes when complete

## Configuration

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| URL | string | - | Starting URL to scrape |
| Max Pages | 1-1000 | 100 | Limit total pages |
| Max Depth | 0-10 | 3 | Link depth from start URL (0 = start page only) |
| Scope | SUBPAGES, HOSTNAME, DOMAIN | HOSTNAME | How far to crawl |
| Include Patterns | glob patterns | - | Only scrape matching URLs |
| Exclude Patterns | glob patterns | - | Skip matching URLs |
| Scrape Mode | AUTO, FAST, FULL | AUTO | How to fetch pages |
| Cookies | string | - | For authenticated sites |
| Force Rescrape | boolean | false | Re-scrape even if unchanged |

**Scope values:**
- `SUBPAGES` - Only pages under the starting path
- `HOSTNAME` - All pages on same hostname
- `DOMAIN` - Include subdomains

**Scrape Mode values:**
- `AUTO` - Try fast mode, fall back to full for SPAs
- `FAST` - HTTP only, faster but may miss JavaScript content
- `FULL` - Uses headless browser, handles all JavaScript

## GraphQL API

Start a scrape job programmatically:

```graphql
mutation StartScrape($input: StartScrapeInput!) {
  startScrape(input: $input) {
    jobId
    baseUrl
    status
  }
}
```

Variables:
```json
{
  "input": {
    "url": "https://docs.example.com",
    "maxPages": 100,
    "maxDepth": 3,
    "scope": "HOSTNAME",
    "includePatterns": ["/docs/*", "/api/*"],
    "excludePatterns": ["/blog/*", "/changelog/*"],
    "scrapeMode": "AUTO",
    "cookies": "session=abc123; auth=xyz789",
    "forceRescrape": false
  }
}
```

Check job status:
```graphql
query GetScrapeJob($jobId: ID!) {
  getScrapeJob(jobId: $jobId) {
    job {
      jobId
      status
      totalUrls
      processedCount
      failedCount
    }
  }
}
```

List jobs:
```graphql
query ListScrapeJobs($limit: Int) {
  listScrapeJobs(limit: $limit) {
    items {
      jobId
      baseUrl
      status
      processedCount
      totalUrls
    }
  }
}
```

Cancel a job:
```graphql
mutation CancelScrape($jobId: ID!) {
  cancelScrape(jobId: $jobId) {
    jobId
    status
  }
}
```

### Authentication

Include your API key in the request headers:
```
x-api-key: da2-xxxxxxxxxxxx
```

Get your API key from **Dashboard → Settings → API Key**.

## How It Works

```text
Start URL → Discovery Queue → Process Queue → S3 → Knowledge Base
```

1. **ScrapeStart** - Creates job, queues initial URL
2. **ScrapeDiscover** - Finds links, respects scope/depth, queues new URLs
3. **ScrapeProcess** - Fetches content, converts to markdown, saves to S3
4. **ProcessDocument** - Standard pipeline indexes the markdown

## Deduplication

Content is hashed using SHA-256. Re-scraping skips unchanged pages (hash match) unless "Force Rescrape" is enabled.

## Real-time Updates

Progress publishes via GraphQL subscriptions. The UI updates automatically as pages process.

## Troubleshooting

### Scrape stuck at 0%
- Check ScrapeDiscover Lambda logs
- Verify URL is accessible

### Pages missing
- Check scope setting (subpages is restrictive)
- Increase max depth
- Some SPAs need "full" mode

### Content garbled
- Try "full" mode for JavaScript-heavy sites
