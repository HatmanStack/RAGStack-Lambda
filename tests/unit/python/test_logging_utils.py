"""Unit tests for logging_utils module."""

from ragstack_common.logging_utils import (
    DEFAULT_SENSITIVE_KEYS,
    log_summary,
    mask_value,
    safe_log_event,
)


class TestMaskValue:
    """Tests for mask_value function."""

    def test_sensitive_key_long_string_shows_partial(self):
        """Long sensitive strings show first 10 chars + length."""
        result = mask_value("access_token", "abcdefghijklmnopqrstuvwxyz")
        assert result == "abcdefghij...(26 chars)"

    def test_sensitive_key_short_string_shows_stars(self):
        """Short sensitive strings are fully masked."""
        result = mask_value("password", "secret123")
        assert result == "***"

    def test_sensitive_key_with_list_shows_type(self):
        """Lists under sensitive keys show type indicator."""
        result = mask_value("token", [1, 2, 3])
        assert result == "[list: masked]"

    def test_sensitive_key_with_dict_shows_type(self):
        """Dicts under sensitive keys show type indicator."""
        result = mask_value("body", {"a": 1})
        assert result == "[dict: masked]"

    def test_sensitive_key_with_non_string_primitive(self):
        """Non-string primitives under sensitive keys are masked."""
        result = mask_value("secret", 42)
        assert result == "***"

    def test_non_sensitive_key_passes_through(self):
        """Non-sensitive keys return value unchanged."""
        result = mask_value("document_id", "doc-123")
        assert result == "doc-123"

    def test_nested_dict_recurses(self):
        """Nested dicts are recursively processed."""
        result = mask_value("data", {"password": "secret", "name": "Alice"})
        assert result["password"] == "***"
        assert result["name"] == "Alice"

    def test_substring_matching(self):
        """Sensitive key substrings match broader key names."""
        result = mask_value("user_query", "what is the meaning of life and the universe")
        assert "..." in result  # Should be masked as partial

    def test_custom_sensitive_keys(self):
        """Custom sensitive_keys parameter overrides defaults."""
        result = mask_value("ssn", "123-45-6789", sensitive_keys=frozenset({"ssn"}))
        assert result == "***"

    def test_custom_sensitive_keys_does_not_mask_default(self):
        """Custom sensitive_keys does not include default keys."""
        result = mask_value("password", "secret123", sensitive_keys=frozenset({"ssn"}))
        assert result == "secret123"

    def test_list_propagates_parent_key(self):
        """List items use parent key context for masking."""
        result = mask_value("tokens", ["abc", "def"])
        assert result == "[list: masked]"


class TestSafeLogEvent:
    """Tests for safe_log_event function."""

    def test_normal_dict_event(self):
        """Normal dict events are processed with masking."""
        event = {"document_id": "doc-1", "query": "sensitive question about life"}
        result = safe_log_event(event)
        assert result["document_id"] == "doc-1"
        assert "..." in result["query"]

    def test_non_dict_returns_raw(self):
        """Non-dict input returns a safe fallback."""
        result = safe_log_event("just a string")
        assert "_raw" in result
        assert result["_raw"] == "just a string"

    def test_exception_during_masking_returns_fallback(self):
        """Masking errors return a safe fallback."""

        class BadDict(dict):
            def items(self):
                raise RuntimeError("oops")

        event = BadDict({"key": "value"})
        result = safe_log_event(event)
        assert "_error" in result
        assert "_keys" in result

    def test_custom_sensitive_keys(self):
        """Custom sensitive_keys is passed to mask_value."""
        event = {"ssn": "123-45-6789", "password": "visible"}
        result = safe_log_event(event, sensitive_keys=frozenset({"ssn"}))
        assert result["ssn"] == "***"
        assert result["password"] == "visible"


class TestLogSummary:
    """Tests for log_summary function."""

    def test_all_parameters(self):
        """All parameters produce correct summary."""
        result = log_summary(
            "query_kb",
            success=True,
            duration_ms=150.567,
            item_count=3,
            error=None,
            kb_id="kb-123",
        )
        assert result["operation"] == "query_kb"
        assert result["success"] is True
        assert result["duration_ms"] == 150.57
        assert result["item_count"] == 3
        assert "error" not in result
        assert result["kb_id"] == "kb-123"

    def test_minimal_parameters(self):
        """Operation-only call produces minimal summary."""
        result = log_summary("test_op")
        assert result == {"operation": "test_op", "success": True}

    def test_long_error_truncated(self):
        """Long error strings are truncated at 500 chars."""
        long_error = "x" * 1000
        result = log_summary("fail_op", error=long_error)
        assert len(result["error"]) == 500

    def test_extra_kwargs_primitives(self):
        """Primitive extra kwargs are included directly."""
        result = log_summary("op", kb_id="kb-1", count=5, ratio=0.5, flag=True)
        assert result["kb_id"] == "kb-1"
        assert result["count"] == 5
        assert result["ratio"] == 0.5
        assert result["flag"] is True

    def test_extra_kwargs_list_shows_count(self):
        """List/tuple extra kwargs log count only."""
        result = log_summary("op", items=[1, 2, 3], tags=("a", "b"))
        assert result["items"] == 3
        assert result["tags"] == 2

    def test_extra_kwargs_dict_excluded(self):
        """Dict extra kwargs are excluded."""
        result = log_summary("op", nested={"a": 1})
        assert "nested" not in result
