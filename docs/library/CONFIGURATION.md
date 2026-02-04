# Configuration Module

Configuration management for runtime settings stored in DynamoDB.

## config.py

```python
class ConfigurationManager:
    def __init__(table_name: str | None = None) -> None
    def get_parameter(param_name: str, default: Any = None) -> Any
    def get_effective_config() -> dict[str, Any]
    def update_custom_config(custom_config: dict[str, Any]) -> None
    def get_schema() -> dict[str, Any]
```

**Environment:** `CONFIGURATION_TABLE_NAME`

## Overview

`ConfigurationManager` provides runtime configuration with a three-tier system:

1. **Schema** - Field definitions and validation rules
2. **Default** - System defaults
3. **Custom** - User overrides (persisted in DynamoDB)

Changes apply immediately without redeployment since Lambdas read config on each request.

## Usage

### Initialize

```python
from ragstack_common.config import ConfigurationManager

# Auto-detect table from environment
config = ConfigurationManager()

# Or specify table name
config = ConfigurationManager(table_name="RAGStack-project-config-abc123")
```

### Get Single Parameter

```python
# With default fallback
ocr_backend = config.get_parameter("ocr_backend", default="textract")

# Without default (returns None if not found)
model_id = config.get_parameter("bedrock_ocr_model_id")
```

**Returns:** The effective value (Custom overrides Default, falls back to default arg if neither exist)

### Get Full Configuration

```python
# Get merged Schema + Default + Custom
effective_config = config.get_effective_config()

# Access nested values
chat_model = effective_config["chat_primary_model"]
quotas = effective_config.get("chat_global_quota_daily", 10000)
```

**Returns:** Complete configuration dict with all effective values

### Update Configuration

```python
# Update custom config (admin only)
updates = {
    "ocr_backend": "bedrock",
    "chat_per_user_quota_daily": 200,
    "metadata_extraction_enabled": True
}
config.update_custom_config(updates)
```

**Note:** Only updates the Custom config tier. Does not modify Schema or Default.

### Get Schema

```python
# Get schema for UI rendering
schema = config.get_schema()

# Schema contains field metadata:
# - type: Field data type (string, number, boolean)
# - enum: Allowed values for dropdowns
# - description: Human-readable label
# - order: Display order in UI
# - dependsOn: Conditional rendering {field, value}
```

## Configuration Parameters

See [CONFIGURATION.md](../CONFIGURATION.md) for complete list of user-configurable parameters.

### Common Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ocr_backend` | string | `textract` | OCR backend: `textract` or `bedrock` |
| `bedrock_ocr_model_id` | string | `haiku` | Bedrock OCR model ID |
| `chat_primary_model` | string | `claude-haiku-4-5` | Primary chat model |
| `chat_fallback_model` | string | `nova-lite` | Fallback chat model |
| `metadata_extraction_enabled` | boolean | `true` | Enable metadata extraction |
| `metadata_extraction_mode` | string | `auto` | `auto` or `manual` |
| `filter_generation_enabled` | boolean | `true` | Enable filter generation |
| `multislice_enabled` | boolean | `true` | Enable multi-slice retrieval |
| `multislice_filtered_boost` | float | `1.25` | Score multiplier for filtered results |

## DynamoDB Schema

Configuration stored in DynamoDB table with partition key `Configuration`.

**Items:**
- `Schema` - Field definitions
- `Default` - System defaults
- `Custom` - User overrides

**Example Custom item:**
```json
{
  "Configuration": "Custom",
  "ocr_backend": "bedrock",
  "chat_per_user_quota_daily": 200,
  "metadata_extraction_mode": "manual",
  "metadata_manual_keys": ["topic", "date_range", "location"]
}
```

## Caching

`ConfigurationManager` reads from DynamoDB on every call (no caching). This ensures:
- Changes apply immediately
- Multiple Lambda instances see consistent state
- No cache invalidation needed

For high-frequency reads, consider caching in calling code with short TTL (5-60 seconds).

## Error Handling

```python
try:
    config = ConfigurationManager()
    value = config.get_parameter("chat_primary_model")
except Exception as e:
    # Table not found, permission denied, etc.
    logger.error(f"Config error: {e}")
    value = "default-value"
```

## Thread Safety

`ConfigurationManager` is thread-safe for reads. Concurrent `update_custom_config()` calls may race - use DynamoDB transactions if concurrent updates are needed.

## See Also

- [User Configuration Guide](../CONFIGURATION.md) - User-facing configuration options
- [models.py](./UTILITIES.md#models) - Configuration data models
