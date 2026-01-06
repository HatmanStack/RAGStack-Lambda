"""Multi-Slice Retriever for parallel filtered and unfiltered queries

This module provides a retrieval strategy that runs multiple parallel queries
with different filter configurations to balance precision and recall.

Multi-slice approach:
- Slice 1 (Unfiltered): Baseline vector similarity, no metadata filter
- Slice 2 (Filtered): Apply LLM-generated metadata filter (precision)
- Additional slices can be configured as needed

All slices run in parallel; results are deduplicated by vector ID,
keeping the highest score for duplicates.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import boto3

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_MAX_SLICES = 3


@dataclass
class SliceConfig:
    """Configuration for a retrieval slice."""

    name: str
    use_filter: bool = False
    num_results: int = 5
    description: str = ""


def deduplicate_results(results: list[dict]) -> list[dict]:
    """
    Deduplicate retrieval results by S3 URI, keeping highest score.

    Args:
        results: List of retrieval result dictionaries.

    Returns:
        Deduplicated list with highest score for each unique document.
    """
    if not results:
        return []

    # Use dict to track best result per URI
    best_by_uri: dict[str, dict] = {}

    for result in results:
        # Extract URI as unique identifier
        location = result.get("location", {})
        s3_location = location.get("s3Location", {})
        uri = s3_location.get("uri", "")

        if not uri:
            # No URI - include the result anyway
            uri = f"_no_uri_{id(result)}"

        score = result.get("score", 0.0)

        # Keep result with highest score
        if uri not in best_by_uri or score > best_by_uri[uri].get("score", 0):
            best_by_uri[uri] = result

    # Return deduplicated results sorted by score (descending)
    deduped = list(best_by_uri.values())
    deduped.sort(key=lambda x: x.get("score", 0), reverse=True)

    return deduped


class MultiSliceRetriever:
    """
    Multi-slice retrieval with parallel execution.

    Runs multiple queries with different filter configurations in parallel
    and merges results, keeping the highest score for duplicates.

    Usage:
        retriever = MultiSliceRetriever()
        results = retriever.retrieve(
            query="genealogy documents",
            knowledge_base_id="kb-123",
            data_source_id="ds-456",
            metadata_filter={"topic": {"$eq": "genealogy"}},
            num_results=5
        )
    """

    def __init__(
        self,
        bedrock_agent_client=None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_slices: int = DEFAULT_MAX_SLICES,
        enabled: bool = True,
    ):
        """
        Initialize the multi-slice retriever.

        Args:
            bedrock_agent_client: Bedrock Agent Runtime client. Creates one if not provided.
            timeout_seconds: Timeout per slice in seconds.
            max_slices: Maximum number of slices to execute.
            enabled: Whether multi-slice is enabled. If False, falls back to single query.
        """
        self.bedrock_agent = bedrock_agent_client or boto3.client("bedrock-agent-runtime")
        self.timeout_seconds = timeout_seconds
        self.max_slices = max_slices
        self.enabled = enabled

        logger.info(
            f"Initialized MultiSliceRetriever: timeout={timeout_seconds}s, "
            f"max_slices={max_slices}, enabled={enabled}"
        )

    def retrieve(
        self,
        query: str,
        knowledge_base_id: str,
        data_source_id: str | None,
        metadata_filter: dict | None = None,
        num_results: int = 5,
    ) -> list[dict]:
        """
        Retrieve documents using multi-slice strategy.

        Args:
            query: Search query text.
            knowledge_base_id: Bedrock Knowledge Base ID.
            data_source_id: Data source ID for filtering (optional).
            metadata_filter: LLM-generated metadata filter (optional).
            num_results: Number of results per slice.

        Returns:
            List of deduplicated retrieval results.
        """
        # If disabled or no filter, fall back to single query
        if not self.enabled or metadata_filter is None:
            return self._single_retrieve(
                query=query,
                knowledge_base_id=knowledge_base_id,
                data_source_id=data_source_id,
                metadata_filter=None,
                num_results=num_results,
            )

        # Build slice configurations
        slices = self._build_slice_configs(metadata_filter, num_results)

        # Execute slices in parallel
        all_results = []

        try:
            with ThreadPoolExecutor(max_workers=min(len(slices), self.max_slices)) as executor:
                # Submit all slice retrievals
                futures = {}
                for slice_config in slices[: self.max_slices]:
                    future = executor.submit(
                        self._execute_slice,
                        query=query,
                        knowledge_base_id=knowledge_base_id,
                        data_source_id=data_source_id,
                        slice_config=slice_config,
                        metadata_filter=metadata_filter if slice_config.use_filter else None,
                    )
                    futures[future] = slice_config.name

                # Collect results as they complete
                for future in as_completed(futures, timeout=self.timeout_seconds):
                    slice_name = futures[future]
                    try:
                        results = future.result(timeout=0.1)
                        all_results.extend(results)
                        logger.info(f"Slice '{slice_name}' returned {len(results)} results")
                    except Exception as e:
                        logger.warning(f"Slice '{slice_name}' failed: {e}")
                        # Continue with other slices

        except TimeoutError:
            logger.warning(f"Multi-slice retrieval timed out after {self.timeout_seconds}s")
            # Return whatever we collected so far

        except Exception as e:
            logger.error(f"Multi-slice retrieval error: {e}")
            # Return whatever we collected

        # Deduplicate and return
        deduped = deduplicate_results(all_results)
        logger.info(
            f"Multi-slice retrieval complete: {len(all_results)} total, "
            f"{len(deduped)} after deduplication"
        )

        return deduped

    def _build_slice_configs(
        self,
        metadata_filter: dict | None,
        num_results: int,
    ) -> list[SliceConfig]:
        """
        Build slice configurations based on filter availability.

        Args:
            metadata_filter: The LLM-generated filter (if any).
            num_results: Number of results per slice.

        Returns:
            List of SliceConfig objects.
        """
        slices = [
            # Slice 1: Unfiltered (baseline recall)
            SliceConfig(
                name="unfiltered",
                use_filter=False,
                num_results=num_results,
                description="Baseline vector similarity",
            ),
        ]

        if metadata_filter:
            # Slice 2: With filter (precision)
            slices.append(
                SliceConfig(
                    name="filtered",
                    use_filter=True,
                    num_results=num_results,
                    description="LLM-generated metadata filter",
                )
            )

        return slices

    def _execute_slice(
        self,
        query: str,
        knowledge_base_id: str,
        data_source_id: str | None,
        slice_config: SliceConfig,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        """
        Execute a single retrieval slice.

        Args:
            query: Search query text.
            knowledge_base_id: Knowledge Base ID.
            data_source_id: Data source ID.
            slice_config: Configuration for this slice.
            metadata_filter: Metadata filter to apply (if slice uses filter).

        Returns:
            List of retrieval results.
        """
        try:
            # Build vector search configuration
            vector_config: dict[str, Any] = {
                "numberOfResults": slice_config.num_results,
            }

            # Build filter expression
            filter_expr = self._build_filter(data_source_id, metadata_filter)
            if filter_expr:
                vector_config["filter"] = filter_expr

            # Execute retrieve
            response = self.bedrock_agent.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": vector_config},
            )

            return response.get("retrievalResults", [])

        except Exception as e:
            logger.warning(f"Slice '{slice_config.name}' execution failed: {e}")
            raise

    def _build_filter(
        self,
        data_source_id: str | None,
        metadata_filter: dict | None,
    ) -> dict | None:
        """
        Build the complete filter expression.

        Combines data source filter with metadata filter using $and.

        Args:
            data_source_id: Data source ID for filtering.
            metadata_filter: Additional metadata filter.

        Returns:
            Combined filter expression, or None if no filters.
        """
        filters = []

        # Add data source filter if provided
        if data_source_id:
            filters.append(
                {
                    "equals": {
                        "key": "x-amz-bedrock-kb-data-source-id",
                        "value": data_source_id,
                    }
                }
            )

        # Add metadata filter if provided
        if metadata_filter:
            # Convert S3 Vectors format to Bedrock KB format if needed
            converted = self._convert_filter_format(metadata_filter)
            if converted:
                filters.append(converted)

        if not filters:
            return None

        if len(filters) == 1:
            return filters[0]

        return {"andAll": filters}

    def _convert_filter_format(self, filter_expr: dict) -> dict | None:
        """
        Convert S3 Vectors filter format to Bedrock KB filter format.

        S3 Vectors: {"topic": {"$eq": "genealogy"}}
        Bedrock KB: {"equals": {"key": "topic", "value": "genealogy"}}

        Args:
            filter_expr: Filter in S3 Vectors format.

        Returns:
            Filter in Bedrock KB format.
        """
        if not filter_expr:
            return None

        # Handle logical operators
        if "$and" in filter_expr:
            conditions = filter_expr["$and"]
            converted = [self._convert_filter_format(c) for c in conditions]
            converted = [c for c in converted if c]  # Remove None values
            if not converted:
                return None
            if len(converted) == 1:
                return converted[0]
            return {"andAll": converted}

        if "$or" in filter_expr:
            conditions = filter_expr["$or"]
            converted = [self._convert_filter_format(c) for c in conditions]
            converted = [c for c in converted if c]
            if not converted:
                return None
            if len(converted) == 1:
                return converted[0]
            return {"orAll": converted}

        # Handle field conditions
        for key, value in filter_expr.items():
            if key.startswith("$"):
                continue  # Skip operators at top level

            if isinstance(value, dict):
                # Extract operator and value
                for op, op_value in value.items():
                    if op == "$eq":
                        return {"equals": {"key": key, "value": op_value}}
                    elif op == "$ne":
                        return {"notEquals": {"key": key, "value": op_value}}
                    elif op == "$gt":
                        return {"greaterThan": {"key": key, "value": op_value}}
                    elif op == "$gte":
                        return {"greaterThanOrEquals": {"key": key, "value": op_value}}
                    elif op == "$lt":
                        return {"lessThan": {"key": key, "value": op_value}}
                    elif op == "$lte":
                        return {"lessThanOrEquals": {"key": key, "value": op_value}}
                    elif op == "$in":
                        return {"in": {"key": key, "value": op_value}}
                    elif op == "$nin":
                        return {"notIn": {"key": key, "value": op_value}}
                    elif op == "$exists":
                        # Bedrock KB doesn't have direct exists filter
                        # Skip for now
                        logger.debug(f"Skipping $exists filter for key: {key}")
                        return None
            else:
                # Implicit $eq
                return {"equals": {"key": key, "value": value}}

        return None

    def _single_retrieve(
        self,
        query: str,
        knowledge_base_id: str,
        data_source_id: str | None,
        metadata_filter: dict | None,
        num_results: int,
    ) -> list[dict]:
        """
        Execute a single (non-parallel) retrieval.

        Used when multi-slice is disabled or no filter is provided.

        Args:
            query: Search query text.
            knowledge_base_id: Knowledge Base ID.
            data_source_id: Data source ID.
            metadata_filter: Metadata filter (usually None for single retrieval).
            num_results: Number of results.

        Returns:
            List of retrieval results.
        """
        try:
            vector_config: dict[str, Any] = {
                "numberOfResults": num_results,
            }

            filter_expr = self._build_filter(data_source_id, metadata_filter)
            if filter_expr:
                vector_config["filter"] = filter_expr

            response = self.bedrock_agent.retrieve(
                knowledgeBaseId=knowledge_base_id,
                retrievalQuery={"text": query},
                retrievalConfiguration={"vectorSearchConfiguration": vector_config},
            )

            results = response.get("retrievalResults", [])
            logger.info(f"Single retrieval returned {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Single retrieval failed: {e}")
            return []
