"""Unit tests for content extraction."""

import pytest

from ragstack_common.scraper.extractor import (
    ExtractedContent,
    add_frontmatter,
    extract_content,
    extract_title,
    find_main_content,
    html_to_markdown,
    sanitize_html,
)


class TestExtractTitle:
    """Tests for extract_title function."""

    def test_extracts_og_title(self):
        html = """
        <html>
            <head>
                <meta property="og:title" content="OG Title Here">
                <title>Regular Title</title>
            </head>
            <body><h1>H1 Title</h1></body>
        </html>
        """
        assert extract_title(html) == "OG Title Here"

    def test_extracts_title_tag(self):
        html = """
        <html>
            <head><title>Page Title</title></head>
            <body><h1>H1 Title</h1></body>
        </html>
        """
        assert extract_title(html) == "Page Title"

    def test_extracts_h1_as_fallback(self):
        html = """
        <html>
            <head></head>
            <body><h1>Main Heading</h1></body>
        </html>
        """
        assert extract_title(html) == "Main Heading"

    def test_returns_none_if_missing(self):
        html = "<html><head></head><body><p>No title here</p></body></html>"
        assert extract_title(html) is None

    def test_strips_whitespace(self):
        html = "<html><head><title>  Spaced Title  </title></head></html>"
        assert extract_title(html) == "Spaced Title"


class TestSanitizeHtml:
    """Tests for sanitize_html function."""

    def test_removes_script_tags(self):
        html = "<html><body><script>alert('hi')</script><p>Content</p></body></html>"
        soup = sanitize_html(html)
        assert soup.find("script") is None
        assert "Content" in soup.get_text()

    def test_removes_style_tags(self):
        html = "<html><body><style>.red{color:red}</style><p>Content</p></body></html>"
        soup = sanitize_html(html)
        assert soup.find("style") is None

    def test_removes_nav(self):
        html = "<html><body><nav><a>Link</a></nav><p>Content</p></body></html>"
        soup = sanitize_html(html)
        assert soup.find("nav") is None
        assert "Content" in soup.get_text()

    def test_removes_footer(self):
        html = "<html><body><p>Content</p><footer>Footer stuff</footer></body></html>"
        soup = sanitize_html(html)
        assert soup.find("footer") is None

    def test_removes_header(self):
        html = "<html><body><header>Header stuff</header><p>Content</p></body></html>"
        soup = sanitize_html(html)
        assert soup.find("header") is None

    def test_preserves_main_content(self):
        html = "<html><body><main><p>Main content</p></main></body></html>"
        soup = sanitize_html(html)
        assert soup.find("main") is not None
        assert "Main content" in soup.get_text()

    def test_preserves_article(self):
        html = "<html><body><article><p>Article content</p></article></body></html>"
        soup = sanitize_html(html)
        assert soup.find("article") is not None

    def test_removes_navigation_role(self):
        html = '<html><body><div role="navigation">Nav</div><p>Content</p></body></html>'
        soup = sanitize_html(html)
        assert soup.find(attrs={"role": "navigation"}) is None

    def test_removes_sidebar_class(self):
        html = '<html><body><div class="sidebar">Sidebar</div><p>Content</p></body></html>'
        soup = sanitize_html(html)
        assert soup.find(class_="sidebar") is None


class TestFindMainContent:
    """Tests for find_main_content function."""

    def test_finds_main_element(self):
        html = """
        <html><body>
            <main><p>This is the main content that should be extracted.</p></main>
            <aside>Sidebar</aside>
        </body></html>
        """
        soup = sanitize_html(html)
        main = find_main_content(soup)
        assert "main content" in main.get_text().lower()

    def test_finds_article_element(self):
        html = """
        <html><body>
            <article><p>This is an article with enough content to be found.</p></article>
        </body></html>
        """
        soup = sanitize_html(html)
        main = find_main_content(soup)
        assert "article" in main.get_text().lower()

    def test_finds_role_main(self):
        html = """
        <html><body>
            <div role="main"><p>Main content area with enough text to be found.</p></div>
        </body></html>
        """
        soup = sanitize_html(html)
        main = find_main_content(soup)
        assert "Main content" in main.get_text()

    def test_falls_back_to_body(self):
        html = """
        <html><body>
            <p>Just some content without semantic elements.</p>
        </body></html>
        """
        soup = sanitize_html(html)
        main = find_main_content(soup)
        assert main.name == "body"


class TestHtmlToMarkdown:
    """Tests for html_to_markdown function."""

    def test_converts_headings(self):
        html = "<h1>Title</h1><h2>Subtitle</h2><p>Paragraph</p>"
        md = html_to_markdown(html)
        assert "# Title" in md
        assert "## Subtitle" in md

    def test_converts_lists(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        md = html_to_markdown(html)
        assert "- Item 1" in md
        assert "- Item 2" in md

    def test_converts_ordered_lists(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        md = html_to_markdown(html)
        assert "1. First" in md or "1." in md  # markdownify uses numbers

    def test_converts_paragraphs(self):
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        md = html_to_markdown(html)
        assert "First paragraph" in md
        assert "Second paragraph" in md

    def test_preserves_code_blocks(self):
        html = '<pre><code class="language-python">print("hello")</code></pre>'
        md = html_to_markdown(html)
        assert "print" in md
        assert "hello" in md

    def test_converts_inline_code(self):
        html = "<p>Use the <code>print()</code> function</p>"
        md = html_to_markdown(html)
        assert "`print()`" in md

    def test_removes_excessive_whitespace(self):
        html = "<p>First</p>\n\n\n\n<p>Second</p>"
        md = html_to_markdown(html)
        # Should not have more than 2 consecutive newlines
        assert "\n\n\n" not in md

    def test_empty_html(self):
        md = html_to_markdown("")
        assert md == ""


class TestAddFrontmatter:
    """Tests for add_frontmatter function."""

    def test_adds_source_url(self):
        content = "# Hello\n\nContent here"
        result = add_frontmatter(content, "https://example.com/page")
        assert "source_url: https://example.com/page" in result
        assert result.startswith("---")
        assert "---\n# Hello" in result  # Frontmatter ends with ---\n then content

    def test_adds_title_if_provided(self):
        content = "Content"
        result = add_frontmatter(content, "https://example.com", title="My Title")
        assert 'title: "My Title"' in result

    def test_escapes_quotes_in_title(self):
        content = "Content"
        result = add_frontmatter(content, "https://example.com", title='Title with "quotes"')
        assert 'title: "Title with \\"quotes\\""' in result

    def test_adds_scraped_at(self):
        content = "Content"
        result = add_frontmatter(content, "https://example.com")
        assert "scraped_at:" in result


class TestExtractContent:
    """Tests for extract_content function."""

    def test_full_extraction_pipeline(self):
        html = """
        <html>
            <head><title>Test Page</title></head>
            <body>
                <nav><a>Menu</a></nav>
                <main>
                    <h1>Main Heading</h1>
                    <p>This is the main content of the page that should be extracted.</p>
                </main>
                <footer>Copyright 2024</footer>
            </body>
        </html>
        """
        result = extract_content(html, "https://example.com/test")

        assert isinstance(result, ExtractedContent)
        assert result.title == "Test Page"
        assert result.source_url == "https://example.com/test"
        assert "source_url: https://example.com/test" in result.markdown
        assert "Main Heading" in result.markdown
        assert "main content" in result.markdown.lower()
        assert "Menu" not in result.markdown  # Nav should be removed
        assert "Copyright" not in result.markdown  # Footer should be removed

    def test_preserves_code_blocks(self):
        html = """
        <html>
            <head><title>Code Page</title></head>
            <body>
                <main>
                    <p>Here is some code:</p>
                    <pre><code class="language-python">def hello():
    print("world")</code></pre>
                </main>
            </body>
        </html>
        """
        result = extract_content(html, "https://example.com/code")
        assert "print" in result.markdown
        assert "hello" in result.markdown

    def test_counts_words(self):
        html = """
        <html>
            <head><title>Test</title></head>
            <body><main><p>One two three four five six seven.</p></main></body>
        </html>
        """
        result = extract_content(html, "https://example.com")
        assert result.word_count > 0

    def test_handles_empty_html(self):
        result = extract_content("", "https://example.com")
        assert result.title == "Untitled"
        assert result.source_url == "https://example.com"

    def test_handles_malformed_html(self):
        html = "<p>Unclosed paragraph<div>Nested wrong</p></div>"
        result = extract_content(html, "https://example.com")
        # Should not raise, should produce some output
        assert result.markdown is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
