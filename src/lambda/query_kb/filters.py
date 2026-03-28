"""KB filter generation and configuration management for query_kb.

Handles lazy-loaded filter components, configuration manager,
and filter example caching.
"""

import logging
import os
from typing import Any

try:
    from ._compat import bedrock_agent
except ImportError:
    from _compat import bedrock_agent  # type: ignore[import-not-found]

from ragstack_common.config import ConfigurationManager
from ragstack_common.filter_generator import FilterGenerator
from ragstack_common.key_library import KeyLibrary
from ragstack_common.multislice_retriever import MultiSliceRetriever

logger = logging.getLogger()


def extract_kb_scalar(value: Any) -> str | None:
    """Extract scalar value from KB metadata which returns lists with quoted strings.

    KB returns metadata like: ['"0"'] or ['value1', 'value2']
    This extracts the first value and strips extra quotes.
    """
    if value is None:
        return None
    if isinstance(value, list):
        if not value:
            return None
        value = value[0]
    if isinstance(value, str):
        return value.strip('"')
    return str(value)


# Module-level lazy initialization (reused across Lambda invocations in same container)
_config_manager: ConfigurationManager | None = None


def get_config_manager() -> ConfigurationManager:
    """Lazy-load ConfigurationManager to avoid import-time failures."""
    global _config_manager
    if _config_manager is None:
        table_name = os.environ.get("CONFIGURATION_TABLE_NAME")
        if table_name:
            _config_manager = ConfigurationManager(table_name=table_name)
        else:
            _config_manager = ConfigurationManager()
    return _config_manager


# Filter generation components (lazy-loaded to avoid init overhead if disabled)
_key_library: KeyLibrary | None = None
_filter_generator: FilterGenerator | None = None
_multislice_retriever: MultiSliceRetriever | None = None
_filter_examples_cache: list[Any] | None = None
_filter_examples_cache_time: float | None = None
FILTER_EXAMPLES_CACHE_TTL = 300  # 5 minutes


def _get_filter_components(
    filtered_score_boost: float = 1.25,
) -> tuple[KeyLibrary, FilterGenerator, MultiSliceRetriever]:
    """Lazy-load filter generation components."""
    global _key_library, _filter_generator, _multislice_retriever

    if _key_library is None:
        _key_library = KeyLibrary()

    if _filter_generator is None:
        # Read configured model, falling back to default if not set
        filter_model = get_config_manager().get_parameter("filter_generation_model", default=None)
        _filter_generator = FilterGenerator(key_library=_key_library, model_id=filter_model)

    # Recreate retriever if boost changed
    boost_changed = (
        _multislice_retriever is not None
        and _multislice_retriever.filtered_score_boost != filtered_score_boost
    )
    if _multislice_retriever is None or boost_changed:
        _multislice_retriever = MultiSliceRetriever(
            bedrock_agent_client=bedrock_agent,
            filtered_score_boost=filtered_score_boost,
        )

    return _key_library, _filter_generator, _multislice_retriever


def _get_filter_examples() -> list[Any]:
    """Get filter examples from config with caching."""
    import time

    global _filter_examples_cache, _filter_examples_cache_time

    now = time.time()

    # Return cached examples if fresh
    if (
        _filter_examples_cache is not None
        and _filter_examples_cache_time is not None
        and (now - _filter_examples_cache_time) < FILTER_EXAMPLES_CACHE_TTL
    ):
        return _filter_examples_cache

    # Load from config
    examples = get_config_manager().get_parameter("metadata_filter_examples", default=[])
    _filter_examples_cache = examples if isinstance(examples, list) else []
    _filter_examples_cache_time = now

    logger.debug(f"Loaded {len(_filter_examples_cache)} filter examples from config")
    return _filter_examples_cache
