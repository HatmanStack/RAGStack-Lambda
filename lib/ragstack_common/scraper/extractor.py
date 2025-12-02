"""
HTML to Markdown content extraction.

Handles HTML sanitization and conversion to clean Markdown
suitable for knowledge base ingestion.
"""


def extract_content(html: str, source_url: str) -> str:
    """
    Extract and convert HTML to Markdown with frontmatter.

    Args:
        html: Raw HTML content
        source_url: Original URL (added to frontmatter)

    Returns:
        Markdown content with frontmatter containing source URL
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("Content extraction not yet implemented")


def sanitize_html(html: str) -> str:
    """
    Remove non-content elements from HTML.

    Removes: script, style, nav, footer, header, aside, iframe
    Preserves: main, article, section, code, pre

    Args:
        html: Raw HTML content

    Returns:
        Sanitized HTML
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("HTML sanitization not yet implemented")


def html_to_markdown(html: str) -> str:
    """
    Convert sanitized HTML to Markdown.

    Preserves code blocks, headings, lists, and links.

    Args:
        html: Sanitized HTML content

    Returns:
        Markdown string
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("HTML to Markdown conversion not yet implemented")


def extract_title(html: str) -> str | None:
    """
    Extract page title from HTML.

    Args:
        html: HTML content

    Returns:
        Title string or None if not found
    """
    # TODO: Implement in Phase-2
    raise NotImplementedError("Title extraction not yet implemented")


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
    # TODO: Implement in Phase-2
    raise NotImplementedError("Frontmatter addition not yet implemented")
