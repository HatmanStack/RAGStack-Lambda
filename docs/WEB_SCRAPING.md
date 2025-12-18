# Web Scraping

Scrape websites and index content into the knowledge base.

## Quick Start

1. **Dashboard → Scrape tab → Enter URL**
2. Configure scope and depth
3. Click "Start Scrape"
4. Content auto-indexes when complete

## Configuration

| Setting | Values | Description |
|---------|--------|-------------|
| Scope | subpages, hostname, domain | How far to crawl |
| Max Pages | 1-1000 | Limit total pages |
| Max Depth | 1-10 | Link depth from start URL |
| Mode | auto, fast, full | auto detects SPAs, full uses headless browser |

**Scope explained:**
- `subpages` - Only pages under the starting path
- `hostname` - All pages on same hostname
- `domain` - Include subdomains

## How It Works

```
Start URL → Discovery Queue → Process Queue → S3 → Knowledge Base
```

1. **ScrapeStart** - Creates job, queues initial URL
2. **ScrapeDiscover** - Finds links, respects scope/depth, queues new URLs
3. **ScrapeProcess** - Fetches content, converts to markdown, saves to S3
4. **ProcessDocument** - Standard pipeline indexes the markdown

## Deduplication

Content is hashed. Re-scraping skips unchanged pages unless "Force Rescrape" is enabled.

## Real-time Updates

Progress publishes via GraphQL subscriptions. The UI updates automatically as pages process.

## Troubleshooting

**Scrape stuck at 0%**
- Check ScrapeDiscover Lambda logs
- Verify URL is accessible

**Pages missing**
- Check scope setting (subpages is restrictive)
- Increase max depth
- Some SPAs need "full" mode

**Content garbled**
- Try "full" mode for JavaScript-heavy sites
