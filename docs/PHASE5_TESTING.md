# Phase 5: End-to-End Testing Guide

This document provides step-by-step instructions for testing the chat configuration UI after deployment.

## Prerequisites

Before testing:
1. ✅ Deploy SAM stack: `python publish.py --project-name test-phase5 --admin-email admin@example.com --region us-east-1 --deploy-chat`
2. ✅ Note the Admin UI URL from deployment outputs
3. ✅ Note the Chat CDN URL from deployment outputs

## Test Scenarios

### Scenario 1: Verify Chat Settings Appear

**Goal:** Confirm chat settings are visible when chat is deployed

**Steps:**
1. Navigate to Admin UI URL
2. Sign in with credentials from email
3. Go to Settings page
4. Scroll down past OCR settings

**Expected Results:**
- ✅ Chat settings section is visible below OCR settings
- ✅ See "Require authentication for chat" toggle (disabled by default)
- ✅ See "Primary model" dropdown (default: Claude Haiku 4.5)
- ✅ See "Fallback model" dropdown (default: Amazon Nova Micro)
- ✅ See "Global daily quota" input (default: 10000)
- ✅ See "Per-user daily quota" input (default: 100)
- ✅ See "Theme preset" dropdown (default: light)
- ✅ See "Custom theme overrides" expandable section (collapsed by default)

### Scenario 2: Test Boolean Field (Authentication Toggle)

**Goal:** Verify toggle works and saves correctly

**Steps:**
1. In Settings page, find "Require authentication for chat"
2. Click the toggle to enable it
3. Verify toggle shows "Enabled"
4. Click "Save changes" button
5. Wait for success message
6. Refresh the page

**Expected Results:**
- ✅ Toggle switches from "Disabled" to "Enabled"
- ✅ "Configuration saved successfully" message appears
- ✅ After refresh, toggle still shows "Enabled"
- ✅ Verify in DynamoDB: `chat_require_auth: true` in Default config

### Scenario 3: Test Number Field (Quota Validation)

**Goal:** Verify number input validates correctly

**Steps:**
1. In Settings page, find "Global daily quota"
2. Change value to `-1`
3. Click "Save changes"
4. Observe validation error
5. Change value to `5000` (valid)
6. Click "Save changes"
7. Wait for success message

**Expected Results:**
- ✅ Entering `-1` shows error: "Quota must be between 1 and 1,000,000"
- ✅ Save button shows error: "Please fix validation errors before saving"
- ✅ Entering `5000` clears validation error
- ✅ Save succeeds with "Configuration saved successfully"
- ✅ After refresh, quota shows `5000`

### Scenario 4: Test Enum Fields (Model Selection)

**Goal:** Verify dropdown selectors work

**Steps:**
1. In Settings page, find "Primary model"
2. Click dropdown and select "Claude Sonnet 4"
3. Find "Fallback model"
4. Click dropdown and select "Amazon Nova Lite"
5. Click "Save changes"
6. Wait for success message
7. Refresh page

**Expected Results:**
- ✅ Dropdowns show available model options
- ✅ Selected models are saved
- ✅ After refresh, selections persist

### Scenario 5: Test Object Field (Theme Overrides)

**Goal:** Verify nested inputs work and validate

**Steps:**
1. In Settings page, find "Custom theme overrides"
2. Click to expand the section
3. Find "primaryColor" input
4. Enter `#ff0000` (valid hex color)
5. Find "fontFamily" input
6. Enter `Roboto, sans-serif`
7. Find "spacing" dropdown
8. Select "spacious"
9. Click "Save changes"
10. Wait for success message

**Expected Results:**
- ✅ Section expands to show nested inputs
- ✅ Valid hex color is accepted
- ✅ Valid font family is accepted
- ✅ Spacing dropdown works
- ✅ Save succeeds
- ✅ After refresh, all overrides persist

### Scenario 6: Test Theme Override Validation

**Goal:** Verify theme validation catches invalid values

**Steps:**
1. In Settings page, expand "Custom theme overrides"
2. Enter `blue` in primaryColor field (invalid - not hex)
3. Click "Save changes"
4. Observe validation error
5. Change to `#0073bb` (valid)
6. Click "Save changes"

**Expected Results:**
- ✅ Invalid color shows error: "Primary color must be a valid hex color"
- ✅ Save is blocked
- ✅ Valid color clears error
- ✅ Save succeeds

### Scenario 7: Test Chat Visibility (chat_deployed Flag)

**Goal:** Verify chat settings only show when chat is deployed

**Steps:**
1. Use AWS CLI to set `chat_deployed` to `false`:
   ```bash
   TABLE=$(aws cloudformation describe-stacks --stack-name RAGStack-test-phase5 \
     --query 'Stacks[0].Outputs[?OutputKey==`ConfigurationTableName`].OutputValue' \
     --output text --region us-east-1)

   aws dynamodb update-item --table-name $TABLE \
     --key '{"Configuration":{"S":"Default"}}' \
     --update-expression "SET chat_deployed = :val" \
     --expression-attribute-values '{":val":{"BOOL":false}}' \
     --region us-east-1
   ```
2. Refresh Settings page
3. Verify chat settings are hidden
4. Set `chat_deployed` back to `true`
5. Refresh Settings page

**Expected Results:**
- ✅ When `chat_deployed = false`, chat settings are NOT visible
- ✅ When `chat_deployed = true`, chat settings ARE visible
- ✅ `chat_model_id` is always visible (not hidden)

### Scenario 8: Test Runtime Effect (Quota Enforcement)

**Goal:** Verify configuration changes affect chat behavior

**Prerequisites:**
- Deploy chat component on a test HTML page
- Chat CDN URL from deployment

**Steps:**
1. In Settings page, set "Global daily quota" to `2`
2. Save changes
3. In test HTML page with chat component:
   ```html
   <script src="https://YOUR_CDN_URL/amplify-chat.js"></script>
   <amplify-chat conversation-id="test"></amplify-chat>
   ```
4. Send 3 messages
5. Observe the third message response

**Expected Results:**
- ✅ First 2 messages use primary model
- ✅ Third message uses fallback model
- ✅ Response indicates "Using fallback model" (if UI implements this)

### Scenario 9: Test Configuration Persistence in DynamoDB

**Goal:** Verify changes are written to DynamoDB correctly

**Steps:**
1. Make several configuration changes in UI
2. Save changes
3. Use AWS CLI to verify:
   ```bash
   TABLE=$(aws cloudformation describe-stacks --stack-name RAGStack-test-phase5 \
     --query 'Stacks[0].Outputs[?OutputKey==`ConfigurationTableName`].OutputValue' \
     --output text --region us-east-1)

   aws dynamodb get-item --table-name $TABLE \
     --key '{"Configuration":{"S":"Custom"}}' \
     --region us-east-1
   ```

**Expected Results:**
- ✅ Custom configuration item exists in DynamoDB
- ✅ Only changed values are in Custom (not duplicating defaults)
- ✅ Values match what was entered in UI

## Validation Test Cases

### Valid Inputs

| Field | Valid Value | Expected |
|-------|-------------|----------|
| Primary Color | `#0073bb` | Accepted |
| Primary Color | `#fff` | Accepted |
| Font Family | `Inter, system-ui` | Accepted |
| Font Family | `"Roboto", sans-serif` | Accepted |
| Global Quota | `10000` | Accepted |
| Global Quota | `1` | Accepted (min) |
| Global Quota | `1000000` | Accepted (max) |
| Per-User Quota | `100` | Accepted |

### Invalid Inputs

| Field | Invalid Value | Expected Error |
|-------|---------------|----------------|
| Primary Color | `blue` | "Primary color must be a valid hex color" |
| Primary Color | `0073bb` (no #) | "Primary color must be a valid hex color" |
| Font Family | `font<script>` | "Font family contains invalid characters" |
| Global Quota | `-1` | "Quota must be between 1 and 1,000,000" |
| Global Quota | `0` | "Quota must be between 1 and 1,000,000" |
| Global Quota | `1000001` | "Quota must be between 1 and 1,000,000" |
| Global Quota | `100.5` | "Quota must be a whole number" |

## Troubleshooting

### Chat settings don't appear
- **Check:** `chat_deployed` flag in DynamoDB Default config
- **Fix:** Run `python publish.py` with `--deploy-chat` flag

### Changes don't save
- **Check:** Browser console for GraphQL errors
- **Check:** Lambda execution logs for configuration_resolver
- **Fix:** Verify Lambda has DynamoDB permissions

### Changes save but don't affect chat
- **Wait:** Configuration cache is 60 seconds
- **Check:** Conversation Lambda is reading from correct table
- **Verify:** DynamoDB Custom config contains your changes

### Validation errors won't clear
- **Refresh:** Page to reset validation state
- **Check:** Ensure value is actually valid
- **Verify:** JavaScript console for errors

## Success Criteria

Phase 5 is complete when:
- ✅ All field types render correctly (boolean, number, enum, object)
- ✅ Chat fields conditionally visible based on `chat_deployed`
- ✅ Validation prevents invalid values from being saved
- ✅ Changes persist across page refreshes
- ✅ Changes written to DynamoDB Custom config
- ✅ All unit tests pass (68 tests)
- ✅ ESLint reports no errors
- ✅ Chat behavior reflects configuration changes (with cache delay)

## Next Steps

After Phase 5 testing is complete:
1. Document any issues found
2. Verify production deployment with `--project-name production`
3. Share embed code with frontend teams
4. Monitor CloudWatch logs for configuration access patterns
5. Set up CloudWatch alarms for quota threshold warnings
