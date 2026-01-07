"""
XML extractor with smart extraction.

Analyzes XML structure and generates descriptive markdown
with hierarchy summaries and element counts.
"""

import xml.etree.ElementTree as ET
from collections import Counter

from .base import BaseExtractor, ExtractionResult


class XmlExtractor(BaseExtractor):
    """Extract content from XML files with hierarchy analysis.

    Features:
    - Extract root element name
    - Count child elements
    - List unique element names with occurrence counts
    - Extract namespace declarations
    - Identify attributes on elements
    """

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from XML file bytes.

        Args:
            content: Raw XML content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Decode content
        text = self._decode_content(content)
        title = self._extract_title_from_filename(filename)

        # Try to parse XML
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            # Fall back to plain text with warning
            return self._create_fallback_result(text, filename, title, str(e))

        # Analyze structure
        root_element = self._get_local_name(root.tag)
        namespaces = self._extract_namespaces(text)
        element_counts = self._count_elements(root)
        unique_elements = list(element_counts.keys())
        element_count = sum(element_counts.values())
        attributes = self._extract_attributes(root)

        # Build structural metadata
        structural_metadata = {
            "root_element": root_element,
            "element_count": element_count,
            "unique_elements": unique_elements,
            "namespaces": namespaces,
            "attributes": attributes,
        }

        # Generate markdown
        markdown_body = self._generate_markdown(
            filename, root_element, namespaces, element_counts, attributes, root
        )
        word_count = self._count_words(markdown_body)

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "xml",
            "root_element": root_element,
            "element_count": element_count,
            "unique_elements": unique_elements[:20],  # Limit for frontmatter
        }
        if namespaces:
            frontmatter_metadata["namespaces"] = namespaces

        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="xml",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )

    def _get_local_name(self, tag: str) -> str:
        """Get local name from potentially namespaced tag."""
        if "}" in tag:
            return tag.split("}")[1]
        return tag

    def _extract_namespaces(self, text: str) -> list[str]:
        """Extract namespace URIs from XML text."""
        namespaces = []
        import re

        # Find xmlns declarations
        pattern = r'xmlns(?::[a-zA-Z0-9_-]+)?=["\']([^"\']+)["\']'
        for match in re.finditer(pattern, text):
            ns = match.group(1)
            if ns not in namespaces:
                namespaces.append(ns)

        return namespaces

    def _count_elements(self, element: ET.Element) -> dict[str, int]:
        """Count occurrences of each element name."""
        counter: Counter = Counter()

        def count_recursive(el: ET.Element) -> None:
            name = self._get_local_name(el.tag)
            counter[name] += 1
            for child in el:
                count_recursive(child)

        count_recursive(element)
        return dict(counter)

    def _extract_attributes(self, root: ET.Element) -> dict[str, list[str]]:
        """Extract attribute names for each element type."""
        attributes: dict[str, set[str]] = {}

        def extract_recursive(el: ET.Element) -> None:
            name = self._get_local_name(el.tag)
            if el.attrib:
                if name not in attributes:
                    attributes[name] = set()
                attributes[name].update(el.attrib.keys())
            for child in el:
                extract_recursive(child)

        extract_recursive(root)
        return {k: list(v) for k, v in attributes.items()}

    def _generate_markdown(
        self,
        filename: str,
        root_element: str,
        namespaces: list[str],
        element_counts: dict[str, int],
        attributes: dict[str, list[str]],
        root: ET.Element,
    ) -> str:
        """Generate descriptive markdown from XML structure."""
        lines = []

        # Title
        total_elements = sum(element_counts.values())
        child_count = len(list(root))
        lines.append(f"# Data: {filename}")
        lines.append("")
        lines.append(f"XML document with root element `{root_element}`.")
        lines.append("")

        # Structure overview
        lines.append("## Structure")
        lines.append("")
        lines.append(f"- **Root:** `{root_element}` ({child_count} direct children)")
        lines.append(f"- **Total elements:** {total_elements}")
        lines.append(f"- **Unique element types:** {len(element_counts)}")

        if namespaces:
            lines.append(f"- **Namespaces:** {len(namespaces)}")
            for ns in namespaces[:5]:
                lines.append(f"  - `{ns}`")
            if len(namespaces) > 5:
                lines.append(f"  - ... and {len(namespaces) - 5} more")

        lines.append("")

        # Elements section
        lines.append("## Elements")
        lines.append("")

        # Sort by count descending
        sorted_elements = sorted(element_counts.items(), key=lambda x: -x[1])

        for name, count in sorted_elements[:20]:  # Limit to top 20
            attrs = attributes.get(name, [])
            if attrs:
                attrs_str = f" - attributes: {', '.join(attrs[:5])}"
                if len(attrs) > 5:
                    attrs_str += ", ..."
            else:
                attrs_str = ""
            lines.append(f"- `{name}` ({count} occurrence{'s' if count != 1 else ''}){attrs_str}")

        if len(sorted_elements) > 20:
            lines.append(f"- ... and {len(sorted_elements) - 20} more element types")

        return "\n".join(lines)

    def _create_fallback_result(self, text: str, filename: str, title: str, error: str) -> ExtractionResult:
        """Create fallback result when XML parsing fails."""
        word_count = self._count_words(text)
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "xml",
            "parse_warning": f"Invalid XML: {error}",
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\n{text}"

        return ExtractionResult(
            markdown=markdown,
            file_type="xml",
            title=title,
            word_count=word_count,
            structural_metadata={},
            parse_warning=f"Invalid XML: {error}",
        )
