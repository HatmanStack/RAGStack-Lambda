# Configuration Integration Testing Checklist

## Prerequisites
- Stack deployed with all Phase 1-4 changes
- Schema and Default seeded in ConfigurationTable
- At least one test document uploaded

## Test Cases

### 1. Configuration Loading
- [ ] Navigate to Settings page
- [ ] Verify all fields render (5 fields total)
- [ ] Verify default values are shown
- [ ] Check browser console for errors

### 2. Configuration Saving
- [ ] Change ocr_backend to "bedrock"
- [ ] Select a bedrock_ocr_model_id
- [ ] Click "Save changes"
- [ ] Verify success message appears
- [ ] Reload page and verify changes persist

### 3. Lambda Functions Use Config

#### process_document Lambda
- [ ] Upload a document
- [ ] Check CloudWatch logs for process_document Lambda
- [ ] Verify log shows "Using OCR backend: bedrock"
- [ ] Verify document processes successfully

#### generate_embeddings Lambda
- [ ] Change text_embed_model_id to "cohere.embed-english-v3"
- [ ] Save configuration
- [ ] Upload a new document
- [ ] Check generate_embeddings Lambda logs
- [ ] Verify log shows "Using text embedding model: cohere.embed-english-v3"

#### query_kb Lambda
- [ ] Change response_model_id to "anthropic.claude-3-5-sonnet-20241022-v2:0"
- [ ] Save configuration
- [ ] Perform a search query
- [ ] Check query_kb Lambda logs
- [ ] Verify log shows "Using response model: anthropic.claude-3-5-sonnet-20241022-v2:0"
- [ ] Verify response includes generated text (from retrieve_and_generate API)

### 4. Embedding Model Integration
- [ ] Change text_embed_model_id to "cohere.embed-english-v3"
- [ ] Save configuration
- [ ] Upload a new document
- [ ] Check generate_embeddings Lambda logs
- [ ] Verify log shows "Using text embedding model: cohere.embed-english-v3"

### 5. Response Model Integration
- [ ] Change response_model_id
- [ ] Save configuration
- [ ] Perform a search query
- [ ] Check query_kb Lambda logs
- [ ] Verify response model is used

### 6. Error Handling
- [ ] Stop DynamoDB ConfigurationTable (simulate failure)
- [ ] Trigger Lambda
- [ ] Verify Lambda logs show clear error message
- [ ] Restart table

### 7. Default Fallback Behavior
- [ ] Remove Custom configuration from DynamoDB (delete Custom item)
- [ ] Upload a document
- [ ] Verify Lambda functions use Default values from ConfigurationTable
- [ ] Check logs show default models being used

### 8. Runtime Configuration Changes
- [ ] Upload document with ocr_backend=textract
- [ ] While processing, change ocr_backend to bedrock in Settings
- [ ] Upload another document immediately
- [ ] Verify second document uses bedrock (no caching)
- [ ] Check both documents processed with correct backends

### 9. retrieve_and_generate API Verification
- [ ] Perform a search query via UI
- [ ] Check query_kb Lambda logs
- [ ] Verify "retrieve_and_generate" API call in logs (not just "retrieve")
- [ ] Verify response includes generated answer text
- [ ] Verify response includes source document citations

## Success Criteria
All checkboxes above checked ✓

## Notes

- If any test fails, check CloudWatch logs for detailed error messages
- ConfigurationTable permissions should be DynamoDBReadPolicy for all processing Lambdas
- All Lambdas should have CONFIGURATION_TABLE_NAME environment variable set
- The retrieve_and_generate API requires modelArn parameter with correct region
- Empty citations in retrieve_and_generate response is valid (means no relevant docs found)
