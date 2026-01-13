"""Filter Generator for query-time metadata filtering

This module provides LLM-based filter generation from natural language queries.
It analyzes user queries and produces S3 Vectors compatible filter expressions
using available metadata keys from the key library.

The generator:
- Uses Claude Haiku for cost-efficient filter generation
- Validates filters against the key library
- Supports filter examples for few-shot learning
- Returns None when no filter intent is detected
"""

import json
import logging
import time

from ragstack_common.bedrock import BedrockClient
from ragstack_common.key_library import KeyLibrary

logger = logging.getLogger(__name__)

# Default model for filter generation (cost-efficient)
DEFAULT_FILTER_MODEL = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

# S3 Vectors filter syntax documentation for prompts
S3_VECTORS_FILTER_SYNTAX = """
S3 Vectors Filter Syntax:
- Comparison operators: $eq (equals), $ne (not equals), $gt (greater than),
  $gte (greater or equal), $lt (less than), $lte (less or equal)
- Set operators: $in (value in list), $nin (value not in list)
- Existence: $exists (true/false - check if field exists)
- Logical operators: $and (all conditions must match), $or (any condition matches)

ARRAY FIELDS (people_mentioned, surnames, locations, tags):
- These fields store multiple values as arrays
- Use $eq to match ANY element in the array
- Example: {"people_mentioned": {"$eq": "jack"}} matches documents where "jack" is one of the people

Example filters:
1. Simple equality: {"topic": {"$eq": "genealogy"}}
2. Match person in array: {"people_mentioned": {"$eq": "jack wilson"}}
3. Match surname in array: {"surnames": {"$eq": "wilson"}}
4. Multiple conditions: {"$and": [{"topic": {"$eq": "genealogy"}},
   {"document_type": {"$eq": "letter"}}]}
5. Multiple possible values: {"topic": {"$in": ["genealogy", "immigration"]}}
6. Existence check: {"location": {"$exists": true}}
"""

# Valid filter operators
VALID_OPERATORS = frozenset(
    {"$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$in", "$nin", "$exists", "$and", "$or"}
)

# Media-specific filter examples for few-shot learning
MEDIA_FILTER_EXAMPLES = """
Media Query Filter Examples:

1. Search transcript content only:
   Query: "What did John say in the interview?"
   Filter: {"content_type": {"$eq": "transcript"}}

2. Search visual content only:
   Query: "Find similar scenes to this meeting"
   Filter: {"content_type": {"$eq": "visual"}}

3. Search within timestamp range:
   Query: "What was discussed between 5 and 10 minutes?"
   Filter: {"$and": [{"timestamp_start": {"$gte": 300}}, {"timestamp_end": {"$lte": 600}}]}

4. Search by media type:
   Query: "Find all video content"
   Filter: {"media_type": {"$eq": "video"}}

5. Search by speaker:
   Query: "What did the first speaker say?"
   Filter: {"speaker": {"$eq": "spk_0"}}

6. Combined media filters:
   Query: "Find transcript from the first 5 minutes of the video"
   Filter: {"$and": [{"content_type": {"$eq": "transcript"}}, {"media_type": {"$eq": "video"}}, {"timestamp_end": {"$lte": 300}}]}
"""


def _normalize_filter_value(value):
    """
    Normalize filter values to lowercase for consistent metadata matching.

    Handles strings, lists of strings, and passes through other types unchanged.
    """
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, list):
        return [v.lower() if isinstance(v, str) else v for v in value]
    return value


# System prompt for filter generation
FILTER_SYSTEM_PROMPT = f"""You are a metadata filter generator. Analyze user queries and generate
S3 Vectors compatible filter JSON expressions when appropriate.

{S3_VECTORS_FILTER_SYNTAX}

IMPORTANT RULES:
1. Return ONLY valid JSON - no explanations or markdown
2. Return "null" (without quotes) if the query has no clear filter intent
3. Use only the available metadata keys provided
4. Prefer simple filters over complex ones
5. For ARRAY fields (people_mentioned, surnames, locations, tags): use $eq to match elements
6. For non-array fields: use $eq for exact match, $in for multiple possible values
7. Do not guess or invent filter values not suggested by the query
8. ALL STRING VALUES MUST BE LOWERCASE - metadata is stored in lowercase

OUTPUT FORMAT:
Return a valid JSON filter object, or the literal string null if no filter applies.
Examples of valid outputs:
- {{"topic": {{"$eq": "genealogy"}}}}
- {{"people_mentioned": {{"$eq": "jack wilson"}}}} (matches if "jack wilson" is in the array)
- {{"surnames": {{"$eq": "wilson"}}}} (matches if "wilson" is in the surnames array)
- {{"$and": [{{"document_type": {{"$eq": "letter"}}}}, {{"surnames": {{"$eq": "wilson"}}}}]}}
- null

DO NOT include any text outside the JSON object or null."""


class FilterGenerator:
    """
    LLM-based filter generator for query-time metadata filtering.

    Uses Claude Haiku to analyze queries and generate S3 Vectors
    compatible filter expressions using keys from the key library.

    Usage:
        generator = FilterGenerator()
        filter_expr = generator.generate_filter(
            "show me PDFs about genealogy",
            filter_examples=[...]
        )
    """

    def __init__(
        self,
        bedrock_client: BedrockClient | None = None,
        key_library: KeyLibrary | None = None,
        model_id: str | None = None,
        enabled: bool = True,
    ):
        """
        Initialize the filter generator.

        Args:
            bedrock_client: Bedrock client for LLM calls. Creates one if not provided.
            key_library: Key library for available metadata keys. Creates one if not provided.
            model_id: Bedrock model ID for generation. Uses Claude Haiku by default.
            enabled: Whether filter generation is enabled. If False, generate_filter
                returns None.
        """
        self.bedrock_client = bedrock_client or BedrockClient()
        self.key_library = key_library or KeyLibrary()
        self.model_id = model_id or DEFAULT_FILTER_MODEL
        self.enabled = enabled

        logger.info(f"Initialized FilterGenerator with model: {self.model_id}, enabled: {enabled}")

    def generate_filter(
        self,
        query: str,
        filter_examples: list[dict] | None = None,
    ) -> dict | None:
        """
        Generate a metadata filter from a natural language query.

        Args:
            query: The user's natural language query.
            filter_examples: Optional list of example query-filter pairs for few-shot learning.

        Returns:
            S3 Vectors compatible filter dict, or None if no filter intent detected.
        """
        # Check if enabled
        if not self.enabled:
            logger.debug("Filter generation disabled")
            return None

        # Validate query
        if not query or not query.strip():
            logger.debug("Empty query, returning None")
            return None

        start_time = time.time()
        try:
            # Get available keys from library
            keys_start = time.time()
            active_keys = self.key_library.get_active_keys()
            key_names = [k["key_name"] for k in active_keys]
            keys_duration_ms = (time.time() - keys_start) * 1000

            if not key_names:
                logger.warning("No active keys in library, cannot generate filter")
                return None

            # Build the prompt
            prompt = self._build_prompt(query, active_keys, filter_examples)

            # Call LLM for filter generation
            llm_start = time.time()
            response = self.bedrock_client.invoke_model(
                model_id=self.model_id,
                system_prompt=FILTER_SYSTEM_PROMPT,
                content=[{"text": prompt}],
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=512,
                context="filter_generation",
            )
            llm_duration_ms = (time.time() - llm_start) * 1000

            # Parse the response
            response_text = self.bedrock_client.extract_text_from_response(response)
            filter_expr = self._parse_response(response_text)

            if filter_expr is None:
                total_duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"No filter intent detected. "
                    f"keys={keys_duration_ms:.1f}ms, llm={llm_duration_ms:.1f}ms, "
                    f"total={total_duration_ms:.1f}ms"
                )
                return None

            # Validate and clean the filter
            validated_filter = self._validate_filter(filter_expr, key_names)

            total_duration_ms = (time.time() - start_time) * 1000
            if validated_filter:
                logger.info(
                    f"Generated filter: {json.dumps(validated_filter)}. "
                    f"keys={keys_duration_ms:.1f}ms, llm={llm_duration_ms:.1f}ms, "
                    f"total={total_duration_ms:.1f}ms"
                )
            else:
                logger.info(
                    f"Filter validation removed all keys, returning None. "
                    f"total={total_duration_ms:.1f}ms"
                )

            return validated_filter

        except Exception as e:
            total_duration_ms = (time.time() - start_time) * 1000
            logger.warning(f"Filter generation failed after {total_duration_ms:.1f}ms: {e}")
            return None

    def _build_prompt(
        self,
        query: str,
        active_keys: list[dict],
        filter_examples: list[dict] | None = None,
    ) -> str:
        """
        Build the user prompt for filter generation.

        Args:
            query: User's query.
            active_keys: List of active key dictionaries from key library.
            filter_examples: Optional filter examples for few-shot learning.

        Returns:
            Formatted prompt string.
        """
        # Build available keys section
        keys_info = []
        for key in active_keys:
            key_name = key.get("key_name", "")
            data_type = key.get("data_type", "string")
            samples = key.get("sample_values", [])
            samples_str = ", ".join(str(s) for s in samples[:5])
            keys_info.append(f"- {key_name} ({data_type}): sample values [{samples_str}]")

        keys_section = "\n".join(keys_info)

        # Build examples section if provided
        examples_section = ""
        if filter_examples:
            example_lines = []
            for ex in filter_examples[:5]:  # Limit to 5 examples
                ex_query = ex.get("query", "")
                ex_filter = ex.get("filter", {})
                example_lines.append(f'Query: "{ex_query}"')
                example_lines.append(f"Filter: {json.dumps(ex_filter)}")
                example_lines.append("")
            examples_section = "\n\nEXAMPLES:\n" + "\n".join(example_lines)

        return f"""Available metadata keys:
{keys_section}
{examples_section}
USER QUERY: {query}

Generate a filter for this query using only the available keys above.
Return null if no filter applies."""

    def _parse_response(self, response_text: str) -> dict | None:
        """
        Parse the LLM response into a filter dictionary.

        Args:
            response_text: Raw text response from LLM.

        Returns:
            Parsed filter dict, or None if response indicates no filter.
        """
        if not response_text:
            return None

        # Clean up response
        cleaned = response_text.strip()

        # Handle explicit null response
        if cleaned.lower() == "null":
            return None

        # Remove markdown code blocks if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Handle null after cleanup
        if cleaned.lower() == "null":
            return None

        try:
            filter_expr = json.loads(cleaned)

            if not isinstance(filter_expr, dict):
                logger.warning(f"LLM response is not a dict: {type(filter_expr)}")
                return None

            # Empty dict means no filter
            if not filter_expr:
                return None

            return filter_expr

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse filter response as JSON: {e}")
            logger.debug(f"Raw response: {response_text[:200]}")
            return None

    def _validate_filter(
        self,
        filter_expr: dict,
        valid_keys: list[str] | None = None,
    ) -> dict | None:
        """
        Validate and clean a filter expression.

        - Removes keys not in the key library
        - Validates operator syntax
        - Returns None if filter becomes empty after validation

        Args:
            filter_expr: The filter expression to validate.
            valid_keys: Optional list of valid key names. If None, fetches from key library.

        Returns:
            Validated filter dict, or None if filter is invalid/empty.
        """
        if not filter_expr:
            return None

        if valid_keys is None:
            valid_keys = self.key_library.get_key_names()

        valid_keys_set = set(valid_keys)

        def validate_condition(condition: dict) -> dict | None:
            """Recursively validate a condition."""
            if not isinstance(condition, dict):
                return None

            result = {}

            for key, value in condition.items():
                # Handle logical operators
                if key in ("$and", "$or"):
                    if isinstance(value, list):
                        validated_conditions = []
                        for sub_cond in value:
                            validated = validate_condition(sub_cond)
                            if validated:
                                validated_conditions.append(validated)
                        if validated_conditions:
                            result[key] = validated_conditions
                    continue

                # Handle field conditions
                if key.startswith("$"):
                    # This is an operator at wrong level, skip
                    continue

                # Check if key is valid
                if key not in valid_keys_set:
                    logger.warning(f"Removing invalid key from filter: {key}")
                    continue

                # Validate the operator structure
                if isinstance(value, dict):
                    # Check operators are valid
                    valid_ops = {}
                    for op, op_value in value.items():
                        if op in VALID_OPERATORS:
                            # Normalize string values to lowercase for consistent filtering
                            valid_ops[op] = _normalize_filter_value(op_value)
                        else:
                            logger.warning(f"Removing invalid operator: {op}")
                    if valid_ops:
                        result[key] = valid_ops
                else:
                    # Direct value (implicit $eq)
                    result[key] = {"$eq": _normalize_filter_value(value)}

            return result if result else None

        validated = validate_condition(filter_expr)

        # If we have a logical operator with only one condition, simplify
        if validated and len(validated) == 1:
            key = list(validated.keys())[0]
            if key in ("$and", "$or"):
                conditions = validated[key]
                if len(conditions) == 1:
                    validated = conditions[0]

        return validated
