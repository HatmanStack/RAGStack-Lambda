# Changelog

## [2.3.3] - 2026-02-17

### Fixed

- **Square brackets stripped from filenames during upload**: `sanitize_filename()` in `createUploadUrl` used an overly aggressive allowlist that replaced `[`, `]`, and other valid characters with underscores, causing `inputS3Uri` in DynamoDB to not match the actual S3 object key. Presigned URL downloads then failed with `NoSuchKey`. Replaced allowlist sanitization with minimal control character stripping — path traversal is already handled separately.

## [2.3.2] - 2026-02-06

### Added

- **MCP Registry submission**: Prepared ragstack-mcp for the official Model Context Protocol Registry
  - Added `mcp-name` verification marker for PyPI package validation
  - Created `server.json` with registry schema, environment variable definitions, and transport config
  - Registry name: `io.github.hatmanstack/ragstack`
  - Bumped ragstack-mcp to v0.1.3

## [2.3.1] - 2026-02-04

### Added

- **AdditionalCorsOrigins parameter**: Parent stacks can now pass additional CORS origins for S3 data bucket access
  - Enables uploads from Amplify-hosted or other external frontends when RAGStack is deployed as nested stack
  - Accepts comma-separated URLs (e.g., `https://main.d123.amplifyapp.com,https://example.com`)

- **Custom Cognito email templates**: Admin invite and verification emails now include branding and dashboard URL
  - Invite email includes stack name, dashboard URL, username, and temporary password
  - Verification email includes stack name and verification code
  - Email delayed until UI build completes (when BuildDashboard=true) so dashboard link works immediately

### Changed

- **`chat_allow_document_access` default**: Changed from `False` to `True` - document sources are now downloadable by default

### Fixed

- **ProcessMedia Lambda non-media file crash**: EventBridge S3 events for non-media files no longer crash with `KeyError: 'document_id'`
  - Lambda now properly detects EventBridge events and returns early for non-media files
  - Previously logged "Skipping non-media file" but continued execution and crashed

- **Ingestion retry for "running" job errors**: Fixed retry logic to also catch "running ingestion job" errors
  - Previously only retried on "ongoing" keyword, missing "There is at least one running ingestion job" errors
  - Documents uploaded during active KB sync now properly retry instead of failing with `OCR_COMPLETE` status

## [2.3.0] - 2026-02-04

### Added

- **Comprehensive nested stack support**: StackPrefix parameter now applies to **all** 127+ AWS resources for complete parent/child stack isolation
  - Lambda functions, DynamoDB tables, Step Functions, log groups, SSM parameters, S3 Vectors index, and all other resources
  - Enables deploying RAGStack as a nested CloudFormation stack without uppercase naming conflicts
  - Fully backward compatible: empty StackPrefix uses stack name (existing deployments unaffected)

### Fixed

- **Hardcoded stack name references in IAM permissions**: All ARN references in IAM policies now use StackPrefix conditional pattern
  - CodeBuild log group permissions
  - Lambda ARN permissions for Knowledge Base updates
  - Step Functions log groups and execution ARNs
  - SSM parameter ARNs
  - Budget name environment variables

### Documentation

- **Nested stack deployment guide**: Updated to reflect StackPrefix applies to all resources, not just S3 buckets
  - Added resource naming examples for Lambda, DynamoDB, Step Functions, log groups
  - Clarified StackPrefix requirements and warnings apply to all resources
  - Enhanced troubleshooting section

## [2.2.1] - 2026-01-29

### Fixed

- **Configuration seeder Decimal handling**: Convert float defaults to Decimal when seeding config (fixes deployment failure for `multislice_filtered_boost`)

## [2.2.0] - 2026-01-29

### Added

- **Configurable filtered results boost**: New UI setting in Metadata Query section to adjust score multiplier for filtered results (1.0-2.0 range, default 1.25)
- **Boosted scores in search results**: Frontend now displays boosted relevance scores, reflecting actual ranking

### Fixed

- **Filter generation for name queries**: Strengthened LLM prompt to always generate `people_mentioned` filters when names are mentioned (e.g., "Pictures of Judy" → `{"people_mentioned": {"$eq": "judy"}}`)
- **Filter examples use only allowed keys**: Validation ensures generated examples don't use keys outside the allowlist; prompt explicitly lists allowed keys
- **AppSync config write permission**: Changed from `DynamoDBReadPolicy` to `DynamoDBCrudPolicy` so UI can save filter key settings
- **DynamoDB Decimal handling**: Convert `float` to `Decimal` when writing config, and `Decimal` to `float` when reading boost values

### Changed

- **SchemaVersion bumped to 6**: Existing stacks will re-run seeder on deploy to get new config defaults (`multislice_filtered_boost`, `metadata_filter_examples`, `metadata_filter_keys`)
- **Reindex time estimate**: UI now says "several minutes to hours" instead of "several minutes"
- **Filter examples help text**: Clarified that disabled examples are replaced when regenerating

## [2.1.0] - 2026-01-28

### Added

- **Filter keys allowlist**: Users can now select which metadata keys are used for filter generation via a new multiselect UI in the Filter Examples section
- **Regenerate Examples button**: Manual control over when filter examples are regenerated (decoupled from metadata analysis)
- **`regenerateFilterExamples` mutation**: New GraphQL mutation for on-demand filter example generation using only allowlisted keys

### Changed

- **Separated key discovery from example generation**: `analyzeMetadata` now only updates key library statistics; filter examples require explicit regeneration
- **Automatic filter key cleanup**: When a metadata key is deleted, it's automatically removed from the filter keys allowlist

### Fixed

- **Bedrock client timeout consistency**: Filter example generation now uses same timeout config as other Bedrock calls (10s connect, 300s read)
- **Safe dictionary access in filter generation**: Prevents KeyError when field analysis has missing keys
- **FilterKeyInput error handling**: Added error state display and retry capability; filters out empty key names

## [2.0.2] - 2026-01-28

### Added

- **Delete metadata keys from UI**: New delete button in Metadata Key Statistics table with confirmation modal
- **`$listContains` filter operator**: Support for filtering on array fields (e.g., `surnames`, `people_mentioned`)
- **Manual keys in filter generation**: When extraction mode is "manual", filter generator only sees configured keys

### Fixed

- **Reindex flow simplified**: Extract metadata first, create KB after, single baseline sync (removed redundant per-document API ingestion and finalize sync)
- **Reindex URI parsing**: `_list_text_uris_for_reindex` now uses `document_id` directly instead of parsing from `output_s3_uri` (handles corrupted URIs)
- **Metadata analyzer preserves counts**: No longer overwrites `occurrence_count` from ingestion with sample counts
- **Manual keys in analyzer**: When extraction mode is "manual", only configured keys marked active
- **Delete metadata key auth**: Added `@aws_api_key` directive and `DynamoDBCrudPolicy` for AppSync resolver
- **Cache attribute typo**: Fixed `_cache_time` → `_active_keys_cache_time` in key library

### Changed

- **Multislice merge prioritizes filtered results**: Filtered slice results appear first, then guaranteed minimum from other slices
- **Reindex state machine**: Removed `WaitForFinalizeSync` loop, sync happens once after all metadata extraction

### Documentation

- Promoted manual metadata keys workflow as recommended approach for better search results

## [2.0.1] - 2026-01-27

### Fixed

- OCR fallback paths writing to `output/` instead of `content/` when `output_s3_uri` not set
- Reindex state machine baseline sync using in-Lambda polling (2-minute limit) instead of Step Functions Wait+Poll loop
- Reindex finalize timeout from in-Lambda polling exceeding Lambda limits — moved to Step Functions polling
- Config table reindex lock using wrong partition key (`config_key` instead of `Configuration`)
- Ingestion retry not catching "can't exceed" concurrent request throttle errors
- Migration script missing `content_type` backfill for v1 records
- Migration script using generic `media` content type instead of specific `video`/`audio` types
- `listImages` query failing when any image has null `created_at` (`AWSDateTime!` non-nullable) — added fallback to `updated_at`
- Multislice retriever merging results purely by score, causing filtered metadata matches to be buried by visual similarity matches
- KB retrieval returning too few results due to Bedrock's stricter relevance cutoff at low `numberOfResults` values

### Added

- `scripts/copy_stack_data.py` for copying S3 and DynamoDB data between stacks
- Baseline sync polling loop in reindex state machine (`WaitForSync` → `CheckSyncStatus` → `IsSyncComplete`)
- Finalize sync polling loop in reindex state machine (`WaitForFinalizeSync` → `CheckFinalizeSyncStatus` → `IsFinalizeSyncComplete`)
- `ServiceUnavailableException` retry handling in document ingestion
- `handle_check_sync_status` and `handle_check_finalize_sync` actions in reindex Lambda
- Guaranteed-minimum merge strategy for multislice retrieval — ensures each slice contributes at least 3 results before filling remaining slots by score
- Baseline `.jpg.metadata.json` sidecars for images missing them (content_type, document_id, filename, surnames)

### Changed

- Document table filename column now wraps long names across multiple lines (Cloudscape `wrapLines` + CSS override)
- KB retrieval `numberOfResults` increased from 5 to 25 for both chat and search to improve recall

## [2.0.0] - 2026-01-10

### Breaking Changes

- **Single Data Source Architecture**: Consolidated from two S3 data sources to one
  - S3 paths changed: `output/` and `images/` merged into `content/`
  - All content types now use the same data source with `inclusionPrefixes: ["content/"]`
  - Removed `TextDataSourceId` and `ImageDataSourceId` CloudFormation outputs
  - Removed `TEXT_DATA_SOURCE_ID` and `IMAGE_DATA_SOURCE_ID` Lambda environment variables

- **Unified Metadata Format**: All content now uses `.metadata.json` files
  - Images switched from inline attributes (`IN_LINE_ATTRIBUTE`) to S3 files (`S3_LOCATION`)
  - Image metadata now stored in `content/{imageId}/caption.txt.metadata.json`

### Migration

- **Migration script provided**: `scripts/migrate_v1_to_v2.py` handles S3 file copying and tracking table updates
- **Reindex handles re-ingestion**: After migration, use Settings UI to trigger reindex with fresh metadata
- See [docs/MIGRATION.md](docs/MIGRATION.md) for complete migration guide

### Added

- **`content_type` metadata field**: All content now includes a `content_type` field for filtering
  - Documents: `content_type: "document"`
  - Images: `content_type: "image"`
  - Web pages: `content_type: "web_page"`
- **Simplified query handlers**: Single unified query instead of dual data source queries
- **Optional content_type filtering**: Query by content type using metadata filters
- **Universal reindex**: Reindex now processes all content types (documents, images, scraped pages)
- **Migration script**: `scripts/migrate_v1_to_v2.py` for migrating v1.x deployments

### Removed

- Dual data source architecture (`output/` and `images/` prefixes)
- Multi-slice data source filtering by `x-amz-bedrock-kb-data-source-id`
- `IN_LINE_ATTRIBUTE` metadata type for images

### Changed

- Increased default retrieval results from 5 to 10 for unified queries
- Simplified MultiSliceRetriever to not require data_source_id parameter

## [1.0.0] - Previous

Initial release with dual data source architecture.
