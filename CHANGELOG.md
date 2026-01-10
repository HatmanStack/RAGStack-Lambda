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

- **Requires full re-indexing**: Existing deployments must be re-deployed with fresh data ingestion
- No backwards compatibility with v1.x data structures
- All documents and images must be re-uploaded after deployment

### Added

- **`content_type` metadata field**: All content now includes a `content_type` field for filtering
  - Documents: `content_type: "document"`
  - Images: `content_type: "image"`
  - Web pages: `content_type: "web_page"`
- **Simplified query handlers**: Single unified query instead of dual data source queries
- **Optional content_type filtering**: Query by content type using metadata filters

### Removed

- Dual data source architecture (`output/` and `images/` prefixes)
- Multi-slice data source filtering by `x-amz-bedrock-kb-data-source-id`
- `IN_LINE_ATTRIBUTE` metadata type for images

### Changed

- Increased default retrieval results from 5 to 10 for unified queries
- Simplified MultiSliceRetriever to not require data_source_id parameter

## [1.0.0] - Previous

Initial release with dual data source architecture.
