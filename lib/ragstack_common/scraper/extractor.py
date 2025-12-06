"""
HTML to Markdown content extraction.

Handles HTML sanitization and conversion to clean Markdown
suitable for knowledge base ingestion.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from bs4 import BeautifulSoup
from markdownify import markdownify as md


@dataclass
class ExtractedContent:
    """Result of content extraction."""

    title: str
    markdown: str
    source_url: str
    scraped_at: str
    word_count: int


def extract_title(html: str) -> str | None:
    """
    Extract page title from HTML.

    Priority: og:title > title > h1

    Args:
        html: HTML content

    Returns:
        Title string or None if not found
    """
    soup = BeautifulSoup(html, "lxml")

    # Try og:title first (social sharing title)
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    # Try title tag
    title_tag = soup.find("title")
    if title_tag:
        text = title_tag.get_text(strip=True)
        if text:
            return text

    # Try first h1
    h1 = soup.find("h1")
    if h1:
        text = h1.get_text(strip=True)
        if text:
            return text

    return None


def sanitize_html(html: str) -> BeautifulSoup:
    """
    Remove non-content elements from HTML.

    Removes: script, style, nav, footer, header, aside, iframe, form, button
    Preserves: main, article, section, code, pre

    Args:
        html: Raw HTML content

    Returns:
        Sanitized BeautifulSoup object
    """
    soup = BeautifulSoup(html, "lxml")

    # Elements to remove completely
    remove_tags = [
        "script",
        "style",
        "noscript",
        "iframe",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "button",
        "input",
        "select",
        "textarea",
        "svg",
    ]

    for tag in remove_tags:
        for element in soup.find_all(tag):
            element.decompose()

    # Remove elements by role
    role_selectors = [
        '[role="navigation"]',
        '[role="banner"]',
        '[role="contentinfo"]',
        '[role="complementary"]',
        '[role="search"]',
    ]

    for selector in role_selectors:
        for element in soup.select(selector):
            element.decompose()

    # Remove common non-content classes
    class_selectors = [
        ".sidebar",
        ".nav",
        ".navbar",
        ".menu",
        ".footer",
        ".header",
        ".advertisement",
        ".ads",
        ".cookie-banner",
        ".cookie-notice",
        ".newsletter",
        ".social-share",
        ".comments",
        ".related-posts",
    ]

    for selector in class_selectors:
        for element in soup.select(selector):
            element.decompose()

    return soup


def find_main_content(soup: BeautifulSoup) -> BeautifulSoup:
    """
    Find the main content area of the page.

    Priority: main > article > [role=main] > .content > .post > body

    Args:
        soup: BeautifulSoup object

    Returns:
        BeautifulSoup element containing main content
    """
    # Try semantic main element
    main = soup.find("main")
    if main and len(main.get_text(strip=True)) > 50:
        return main

    # Try article element
    article = soup.find("article")
    if article and len(article.get_text(strip=True)) > 50:
        return article

    # Try role=main
    role_main = soup.find(attrs={"role": "main"})
    if role_main and len(role_main.get_text(strip=True)) > 50:
        return role_main

    # Try common content class names
    content_classes = ["content", "post", "entry", "article-body", "post-content"]
    for class_name in content_classes:
        content_div = soup.find(class_=class_name)
        if content_div and len(content_div.get_text(strip=True)) > 50:
            return content_div

    # Fall back to body
    if soup.body:
        return soup.body

    return soup


def html_to_markdown(html: str) -> str:
    """
    Convert HTML to Markdown using markdownify.

    Preserves code blocks, headings, lists, and links.

    Args:
        html: HTML content (string or element)

    Returns:
        Markdown string
    """
    markdown = md(
        str(html),
        heading_style="ATX",
        bullets="-",
        code_language_callback=_get_code_language,
        escape_asterisks=False,
        escape_underscores=False,
        strip=["a"],  # Remove links but keep text
    )

    # Clean up excessive whitespace
    lines = markdown.split("\n")
    cleaned_lines = []
    prev_blank = False

    for line in lines:
        is_blank = not line.strip()

        # Skip multiple consecutive blank lines
        if is_blank and prev_blank:
            continue

        cleaned_lines.append(line)
        prev_blank = is_blank

    return "\n".join(cleaned_lines).strip()


def _get_code_language(element) -> str:
    """Extract code language from element class."""
    classes = element.get("class", [])
    for cls in classes:
        if cls.startswith("language-"):
            return cls.replace("language-", "")
        if cls.startswith("lang-"):
            return cls.replace("lang-", "")
    return ""


def add_frontmatter(content: str, source_url: str, title: str | None = None) -> str:
    """
    Add YAML frontmatter to Markdown content.

    Args:
        content: Markdown content
        source_url: Original URL
        title: Optional page title

    Returns:
        Markdown with frontmatter
    """
    scraped_at = datetime.now(UTC).isoformat()

    frontmatter_lines = [
        "---",
        f"source_url: {source_url}",
    ]

    if title:
        # Escape quotes in title for YAML
        escaped_title = title.replace('"', '\\"')
        frontmatter_lines.append(f'title: "{escaped_title}"')

    frontmatter_lines.extend(
        [
            f"scraped_at: {scraped_at}",
            "---",
            "",
        ]
    )

    return "\n".join(frontmatter_lines) + content


def extract_content(html: str, source_url: str) -> ExtractedContent:
    """
    Full extraction pipeline: sanitize → find main → convert → add frontmatter.

    Args:
        html: Raw HTML content
        source_url: Original URL (added to frontmatter)

    Returns:
        ExtractedContent with title, markdown, and metadata
    """
    # Extract title before sanitizing (title is in head)
    title = extract_title(html) or "Untitled"

    # Sanitize HTML
    soup = sanitize_html(html)

    # Find main content area
    main_content = find_main_content(soup)

    # Convert to markdown
    markdown_body = html_to_markdown(str(main_content))

    # Count words for metadata
    word_count = len(markdown_body.split())

    # Add frontmatter
    scraped_at = datetime.now(UTC).isoformat()
    full_markdown = add_frontmatter(markdown_body, source_url, title)

    return ExtractedContent(
        title=title,
        markdown=full_markdown,
        source_url=source_url,
        scraped_at=scraped_at,
        word_count=word_count,
    )
