"""
JSON extractor with smart extraction.

Analyzes JSON structure and generates descriptive markdown
with schema summaries and sample data.
"""

import json
from typing import Any

from .base import BaseExtractor, ExtractionResult


class JsonExtractor(BaseExtractor):
    """Extract content from JSON files with structure analysis.

    Features:
    - Detect object vs array root type
    - Document top-level keys with types
    - Describe nested structures up to depth 3
    - Handle malformed JSON with fallback
    """

    MAX_DEPTH = 3

    def extract(self, content: bytes, filename: str) -> ExtractionResult:
        """Extract text content from JSON file bytes.

        Args:
            content: Raw JSON content as bytes.
            filename: Original filename.

        Returns:
            ExtractionResult with markdown content and metadata.
        """
        # Decode content
        text = self._decode_content(content)
        title = self._extract_title_from_filename(filename)

        # Try to parse JSON
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            # Fall back to plain text with warning
            return self._create_fallback_result(text, filename, title, str(e))

        # Analyze structure
        structure_type = "array" if isinstance(data, list) else "object"

        # Build structural metadata
        structural_metadata = {
            "structure_type": structure_type,
        }

        if structure_type == "object":
            top_level_keys = list(data.keys()) if isinstance(data, dict) else []
            structural_metadata["top_level_keys"] = top_level_keys
            structural_metadata["key_count"] = len(top_level_keys)
        else:
            structural_metadata["item_count"] = len(data) if isinstance(data, list) else 0

        # Calculate max depth
        structural_metadata["max_depth"] = self._calculate_depth(data)

        # Generate markdown
        markdown_body = self._generate_markdown(filename, data, structure_type)
        word_count = self._count_words(markdown_body)

        # Build frontmatter metadata
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "json",
            "structure_type": structure_type,
        }
        if structure_type == "object":
            frontmatter_metadata["top_level_keys"] = structural_metadata.get("top_level_keys", [])
        else:
            frontmatter_metadata["item_count"] = structural_metadata.get("item_count", 0)

        frontmatter = self._generate_frontmatter(frontmatter_metadata)

        # Combine frontmatter and content
        markdown = f"{frontmatter}\n{markdown_body}"

        return ExtractionResult(
            markdown=markdown,
            file_type="json",
            title=title,
            word_count=word_count,
            structural_metadata=structural_metadata,
            parse_warning=None,
        )

    def _calculate_depth(self, data: Any, current_depth: int = 0) -> int:
        """Calculate maximum nesting depth of JSON structure."""
        if current_depth >= 10:  # Safety limit
            return current_depth

        if isinstance(data, dict):
            if not data:
                return current_depth + 1
            return max(self._calculate_depth(v, current_depth + 1) for v in data.values())
        if isinstance(data, list):
            if not data:
                return current_depth + 1
            return max(self._calculate_depth(item, current_depth + 1) for item in data)
        return current_depth

    def _generate_markdown(self, filename: str, data: Any, structure_type: str) -> str:
        """Generate descriptive markdown from JSON data."""
        lines = []

        # Title
        if structure_type == "object" and isinstance(data, dict):
            key_count = len(data)
            lines.append(f"# Data: {filename}")
            lines.append("")
            key_word = "key" if key_count == 1 else "keys"
            lines.append(f"JSON object with {key_count} top-level {key_word}.")
        else:
            item_count = len(data) if isinstance(data, list) else 0
            lines.append(f"# Data: {filename}")
            lines.append("")
            lines.append(f"JSON array with {item_count} {'item' if item_count == 1 else 'items'}.")

        lines.append("")

        # Structure description
        lines.append("## Structure")
        lines.append("")

        if isinstance(data, dict):
            self._describe_object(data, lines, depth=0)
        elif isinstance(data, list):
            self._describe_array(data, lines, depth=0)

        return "\n".join(lines)

    def _describe_object(self, obj: dict, lines: list[str], depth: int, prefix: str = "") -> None:
        """Describe object structure."""
        if depth > self.MAX_DEPTH:
            lines.append(f"{prefix}- (nested object - truncated)")
            return

        for key, value in obj.items():
            type_desc = self._get_type_description(value)
            indent = "  " * depth

            if isinstance(value, dict):
                if value:
                    subkeys = list(value.keys())[:5]
                    subkeys_str = ", ".join(subkeys)
                    if len(value) > 5:
                        subkeys_str += ", ..."
                    lines.append(f"{indent}- **{key}** (object): Contains {subkeys_str}")
                    if depth < self.MAX_DEPTH:
                        self._describe_object(value, lines, depth + 1)
                else:
                    lines.append(f"{indent}- **{key}** (object): Empty object")
            elif isinstance(value, list):
                if value:
                    item_type = self._get_type_description(value[0])
                    count = len(value)
                    lines.append(f"{indent}- **{key}** (array): {count} items of {item_type}")
                else:
                    lines.append(f"{indent}- **{key}** (array): Empty array")
            else:
                sample = self._format_sample(value)
                lines.append(f"{indent}- **{key}** ({type_desc}): {sample}")

    def _describe_array(self, arr: list, lines: list[str], depth: int) -> None:
        """Describe array structure."""
        if not arr:
            lines.append("- Empty array")
            return

        if depth > self.MAX_DEPTH:
            lines.append("- (nested array - truncated)")
            return

        # Check if all items are same type
        first_type = type(arr[0])
        all_same_type = all(isinstance(item, first_type) for item in arr)

        if all_same_type:
            type_name = self._get_type_description(arr[0])
            if isinstance(arr[0], dict) and arr[0]:
                # Array of objects - describe common structure
                common_keys = set(arr[0].keys())
                for item in arr[1:5]:  # Check first 5 items
                    if isinstance(item, dict):
                        common_keys &= set(item.keys())

                if common_keys:
                    keys_str = ", ".join(sorted(common_keys)[:10])
                    lines.append(f"Array of {len(arr)} objects with common keys: {keys_str}")
                else:
                    lines.append(f"Array of {len(arr)} objects with varying structure")
            else:
                lines.append(f"Array of {len(arr)} {type_name} values")

                # Show sample values for primitives
                if not isinstance(arr[0], (dict, list)):
                    samples = [self._format_sample(v) for v in arr[:3]]
                    lines.append(f"Sample values: {', '.join(samples)}")
        else:
            lines.append(f"Mixed array with {len(arr)} items of different types")

    def _get_type_description(self, value: Any) -> str:
        """Get human-readable type description."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "unknown"

    def _format_sample(self, value: Any) -> str:
        """Format a sample value for display."""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str):
            if len(value) > 50:
                return f'"{value[:50]}..."'
            return f'"{value}"'
        if isinstance(value, (int, float)):
            return str(value)
        return str(type(value).__name__)

    def _create_fallback_result(
        self, text: str, filename: str, title: str, error: str
    ) -> ExtractionResult:
        """Create fallback result when JSON parsing fails."""
        word_count = self._count_words(text)
        frontmatter_metadata = {
            "source_file": filename,
            "file_type": "json",
            "parse_warning": f"Invalid JSON: {error}",
        }
        frontmatter = self._generate_frontmatter(frontmatter_metadata)
        markdown = f"{frontmatter}\n{text}"

        return ExtractionResult(
            markdown=markdown,
            file_type="json",
            title=title,
            word_count=word_count,
            structural_metadata={},
            parse_warning=f"Invalid JSON: {error}",
        )
