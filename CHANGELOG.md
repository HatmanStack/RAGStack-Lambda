# Changelog

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
