"""Unit tests for ragstack_common.kb_filters module."""

from ragstack_common.kb_filters import extract_kb_scalar


class TestExtractKbScalar:
    """Tests for extract_kb_scalar utility function."""

    def test_none_input_returns_none(self):
        """None input returns None."""
        assert extract_kb_scalar(None) is None

    def test_empty_list_returns_none(self):
        """Empty list returns None."""
        assert extract_kb_scalar([]) is None

    def test_list_with_quoted_string(self):
        """List with quoted string strips quotes: ['"0"'] returns '0'."""
        assert extract_kb_scalar(['"0"']) == "0"

    def test_list_with_unquoted_string(self):
        """List with unquoted string passes through."""
        assert extract_kb_scalar(["hello"]) == "hello"

    def test_regular_string_passes_through(self):
        """Regular string passes through unchanged."""
        assert extract_kb_scalar("test_value") == "test_value"

    def test_quoted_string_strips_quotes(self):
        """Quoted string strips extra quotes."""
        assert extract_kb_scalar('"quoted"') == "quoted"

    def test_integer_converts_to_string(self):
        """Non-string values are converted to string."""
        assert extract_kb_scalar(42) == "42"

    def test_list_with_multiple_values_takes_first(self):
        """List with multiple values returns the first."""
        assert extract_kb_scalar(["first", "second"]) == "first"
