"""Sample content for text extractor testing.

This module provides programmatically generated sample content for various
file types. Following the existing pattern in metadata_samples.py, all content
is defined as string constants rather than binary files.

Binary files (EPUB, DOCX, XLSX) are created within tests using their
respective libraries (ebooklib, python-docx, openpyxl).
"""

# =============================================================================
# PLAIN TEXT SAMPLES
# =============================================================================

SIMPLE_TEXT = """This is a simple text file.
It has multiple lines.
And some basic content for testing."""

UNICODE_TEXT = """Unicode text with special characters:
- Emojis: 🎉 🚀 ✨
- Accented: café résumé naïve
- CJK: 你好世界 こんにちは
- Symbols: © ® ™ € £ ¥"""

EMPTY_TEXT = ""

WHITESPACE_ONLY_TEXT = "   \n\n\t\t\n   "

SINGLE_LINE_TEXT = "Just one line without newline"

# =============================================================================
# HTML SAMPLES
# =============================================================================

FULL_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta property="og:title" content="OG Title for Testing">
    <title>HTML Test Page</title>
    <style>.hidden { display: none; }</style>
</head>
<body>
    <nav>
        <ul><li><a href="/">Home</a></li><li><a href="/about">About</a></li></ul>
    </nav>
    <main>
        <h1>Main Heading</h1>
        <p>This is the main content of the page that should be extracted.</p>
        <h2>Subheading</h2>
        <p>More content with <strong>bold</strong> and <em>italic</em> text.</p>
        <ul>
            <li>List item 1</li>
            <li>List item 2</li>
        </ul>
    </main>
    <aside class="sidebar">
        <p>Sidebar content that should be removed.</p>
    </aside>
    <footer>
        <p>Copyright 2024. Contact: info@example.com</p>
    </footer>
    <script>alert('This should be removed');</script>
</body>
</html>"""

HTML_FRAGMENT = """<div>
    <h2>Fragment Heading</h2>
    <p>This is just an HTML fragment without html/head/body tags.</p>
    <p>It should still be processable.</p>
</div>"""

HTML_WITH_CODE = """<!DOCTYPE html>
<html>
<head><title>Code Example</title></head>
<body>
<main>
    <h1>Code Sample</h1>
    <p>Here is some Python code:</p>
    <pre><code class="language-python">def hello():
    print("Hello, World!")
</code></pre>
    <p>And inline code: <code>print()</code></p>
</main>
</body>
</html>"""

HTML_EMPTY = "<html><head></head><body></body></html>"

HTML_SCRIPTS_ONLY = """<!DOCTYPE html>
<html>
<head><title>Script Page</title></head>
<body>
    <script>console.log('script1');</script>
    <script>console.log('script2');</script>
</body>
</html>"""

# =============================================================================
# CSV SAMPLES
# =============================================================================

CSV_STANDARD = """name,age,city,email
John Doe,30,New York,john@example.com
Jane Smith,25,Los Angeles,jane@example.com
Bob Johnson,45,Chicago,bob@example.com
Alice Brown,35,Houston,alice@example.com
Charlie Wilson,28,Phoenix,charlie@example.com"""

CSV_TAB_SEPARATED = """name\tage\tcity
John\t30\tNew York
Jane\t25\tLos Angeles
Bob\t45\tChicago"""

CSV_SEMICOLON = """name;age;city
John;30;New York
Jane;25;Los Angeles
Bob;45;Chicago"""

CSV_NO_HEADER = """John,30,New York
Jane,25,Los Angeles
Bob,45,Chicago"""

CSV_QUOTED_FIELDS = """name,description,value
"Smith, John","A person named John, who lives in NYC",100
"Doe, Jane","Another person",200"""

CSV_NUMERIC = """id,value,percentage
1,100,0.5
2,200,0.75
3,150,0.6"""

CSV_MALFORMED = """name,age,city
John,30
Jane,25,Los Angeles,extra
Bob"""

CSV_SINGLE_COLUMN = """name
John
Jane
Bob"""

CSV_EMPTY = ""

# =============================================================================
# JSON SAMPLES
# =============================================================================

JSON_SIMPLE_OBJECT = """{
    "name": "John Doe",
    "age": 30,
    "active": true,
    "email": null
}"""

JSON_SIMPLE_ARRAY = """[1, 2, 3, 4, 5]"""

JSON_ARRAY_OF_OBJECTS = """[
    {"id": 1, "name": "Alice"},
    {"id": 2, "name": "Bob"},
    {"id": 3, "name": "Charlie"}
]"""

JSON_NESTED = """{
    "database": {
        "host": "localhost",
        "port": 5432,
        "credentials": {
            "username": "admin",
            "password": "secret"
        }
    },
    "cache": {
        "enabled": true,
        "ttl": 3600
    },
    "features": ["auth", "logging", "metrics"]
}"""

JSON_DEEPLY_NESTED = """{
    "level1": {
        "level2": {
            "level3": {
                "level4": {
                    "level5": {
                        "value": "deep"
                    }
                }
            }
        }
    }
}"""

JSON_ALL_TYPES = """{
    "string": "hello",
    "number_int": 42,
    "number_float": 3.14,
    "boolean_true": true,
    "boolean_false": false,
    "null_value": null,
    "array": [1, "two", true],
    "object": {"nested": "value"}
}"""

JSON_EMPTY_OBJECT = "{}"

JSON_EMPTY_ARRAY = "[]"

JSON_MALFORMED = """{
    "name": "John",
    "age": 30
    missing comma here
}"""

# =============================================================================
# XML SAMPLES
# =============================================================================

XML_SIMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<root>
    <child>Content</child>
</root>"""

XML_NO_DECLARATION = """<root>
    <item>First</item>
    <item>Second</item>
</root>"""

XML_WITH_ATTRIBUTES = """<?xml version="1.0"?>
<catalog>
    <product id="1" category="electronics">
        <name>Laptop</name>
        <price currency="USD">999.99</price>
    </product>
    <product id="2" category="electronics">
        <name>Phone</name>
        <price currency="USD">499.99</price>
    </product>
</catalog>"""

XML_WITH_NAMESPACE = """<?xml version="1.0"?>
<root xmlns="http://example.com/default" xmlns:custom="http://example.com/custom">
    <item>Default namespace item</item>
    <custom:item>Custom namespace item</custom:item>
</root>"""

XML_COMPLEX = """<?xml version="1.0" encoding="UTF-8"?>
<bookstore>
    <book category="fiction">
        <title lang="en">The Great Gatsby</title>
        <author>F. Scott Fitzgerald</author>
        <year>1925</year>
        <price>10.99</price>
    </book>
    <book category="non-fiction">
        <title lang="en">A Brief History of Time</title>
        <author>Stephen Hawking</author>
        <year>1988</year>
        <price>15.99</price>
    </book>
</bookstore>"""

XML_EMPTY_ROOT = "<root/>"

XML_MALFORMED = """<?xml version="1.0"?>
<root>
    <unclosed>
</root>"""

# =============================================================================
# EMAIL SAMPLES
# =============================================================================

EMAIL_SIMPLE = """From: sender@example.com
To: recipient@example.com
Subject: Test Email
Date: Mon, 15 Jan 2024 10:30:00 -0500

This is the plain text body of the email.

Best regards,
Sender"""

EMAIL_WITH_CC = """From: sender@example.com
To: recipient@example.com
Cc: cc1@example.com, cc2@example.com
Bcc: hidden@example.com
Subject: Meeting Notes
Date: Tue, 16 Jan 2024 14:00:00 +0000

Meeting notes from today's discussion.

Action items:
1. Review document
2. Send feedback
3. Schedule follow-up"""

EMAIL_MULTIPART = """From: sender@example.com
To: recipient@example.com
Subject: Multipart Email
Date: Wed, 17 Jan 2024 09:00:00 -0800
MIME-Version: 1.0
Content-Type: multipart/alternative; boundary="boundary123"

--boundary123
Content-Type: text/plain; charset="utf-8"

This is the plain text version.

--boundary123
Content-Type: text/html; charset="utf-8"

<html><body><p>This is the <strong>HTML</strong> version.</p></body></html>

--boundary123--"""

EMAIL_HTML_ONLY = """From: sender@example.com
To: recipient@example.com
Subject: HTML Only Email
Date: Thu, 18 Jan 2024 11:00:00 +0000
MIME-Version: 1.0
Content-Type: text/html; charset="utf-8"

<html>
<body>
<h1>Welcome!</h1>
<p>This email only has HTML content.</p>
<p>Visit <a href="https://example.com">our website</a>.</p>
</body>
</html>"""

EMAIL_WITH_ATTACHMENT = """From: sender@example.com
To: recipient@example.com
Subject: Email with Attachment
Date: Fri, 19 Jan 2024 15:00:00 -0500
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="mixed_boundary"

--mixed_boundary
Content-Type: text/plain

Please see the attached file.

--mixed_boundary
Content-Type: application/octet-stream; name="document.pdf"
Content-Disposition: attachment; filename="document.pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQKMSAwIG9iag==

--mixed_boundary--"""

EMAIL_MINIMAL = """From: a@b.com
To: c@d.com
Subject: Min

Body"""

EMAIL_MALFORMED = """Not really an email
Just some random text
That doesn't have proper headers"""

# =============================================================================
# AMBIGUOUS CONTENT SAMPLES (for sniffer testing)
# =============================================================================

TEXT_WITH_COMMAS = """Hello, my name is John, and I live in Boston.
I enjoy reading, writing, and programming.
Commas are common in natural language, unlike CSV data."""

TEXT_LOOKS_LIKE_JSON = """This is a story about a man named {John}.
He had [many] hobbies.
But this is not JSON."""

TEXT_LOOKS_LIKE_XML = """Compare apples < oranges and oranges > bananas.
This is not XML <but> it has angle brackets.
HTML tags like <div> might confuse detection."""

