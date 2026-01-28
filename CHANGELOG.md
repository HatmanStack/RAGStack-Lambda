# Changelog

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
