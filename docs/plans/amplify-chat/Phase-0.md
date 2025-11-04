# Phase 0: Architecture Decision Records & Prerequisites

**Purpose:** Establish design decisions, architectural patterns, and prerequisites that apply to all implementation phases.

**Audience:** All engineers implementing phases 1-5. Read this completely before starting any phase.

---

## Architecture Decision Records (ADRs)

### ADR-1: Two-Stack Architecture

**Decision:** Separate SAM and Amplify stacks, no shared CloudFormation resources.

**Rationale:**
- Clear separation of concerns (SAM = document processing, Amplify = chat)
- Independent lifecycle management (delete chat without affecting SAM)
- Different deployment tools (SAM CLI vs Amplify CLI)

**Implications:**
- Cross-stack integration via IAM permissions and runtime configuration
- Two CloudFormation stacks to manage
- Amplify Lambda reads from SAM's DynamoDB table

---

### ADR-2: Runtime Configuration via DynamoDB

**Decision:** Store chat configuration in SAM's existing ConfigurationTable, read by Amplify Lambda at runtime.

**Rationale:**
- Single source of truth for all configuration (OCR + chat)
- No Amplify redeployment needed to change settings
- Admin UI already has ConfigurationTable integration

**Implications:**
- Amplify Lambda needs IAM permissions to read ConfigurationTable
- 60-second config cache to minimize DynamoDB reads
- Configuration changes take effect within cache TTL

**Alternative Rejected:** GraphQL-based configuration storage (adds unnecessary complexity)

---

### ADR-3: Web Component Config Bundling

**Decision:** Bundle `amplify_outputs.json` into web component at build time (hardcoded config).

**Rationale:**
- Simplest embedding experience (no runtime config fetch)
- One `<script>` tag, no additional setup
- Config rarely changes after deployment

**Implications:**
- Each deployment gets unique CDN URL with bundled config
- Cannot change Amplify backend URL without rebuilding component
- Different environments (dev/prod) need separate builds

**Alternative Rejected:** Runtime config fetch (adds HTTP request, cache complexity)

---

### ADR-4: CodeBuild Pattern for Web Component

**Decision:** Use CodeBuild to build and deploy web component (matches SAM UI pattern).

**Rationale:**
- Consistent with existing `src/ui/` deployment pattern
- Reproducible builds (not dependent on local environment)
- Build logs in CloudWatch for debugging

**Implications:**
- `publish.py` packages source, uploads to S3
- Amplify `backend.ts` defines CodeBuild project
- Build triggered after Amplify stack deployment

**Alternative Rejected:** Local build with `npm run build` (environment-dependent)

---

### ADR-5: Optional Authentication (Default: Off)

**Decision:** `chat_require_auth` defaults to `false`, supports both anonymous and authenticated modes.

**Rationale:**
- Simplest integration for public websites (no auth setup)
- Flexible for authenticated use cases (pass user token)
- Rate limiting works in both modes (conversation-id or user-id)

**Implications:**
- Web component accepts optional `user-id` and `user-token` attributes
- Backend validates tokens only if `chat_require_auth = true`
- Documentation must cover both integration patterns

**Alternative Rejected:** Auth-required by default (higher barrier to adoption)

---

### ADR-6: Quota Tracking in ConfigurationTable

**Decision:** Store daily usage counters in ConfigurationTable with TTL.

**Rationale:**
- Reuse existing DynamoDB table (no new infrastructure)
- TTL automatically cleans up old quota records
- Simple atomic increment operations

**Implications:**
- Quota records keyed as `quota#global#{date}` and `quota#user#{userId}#{date}`
- 2-day TTL for cleanup
- No separate quota database needed

**Alternative Rejected:** Separate QuotaTable (unnecessary complexity)

---

### ADR-7: Model Degradation Over Hard Limits

**Decision:** Automatically switch to fallback model when quotas exceeded (don't reject requests).

**Rationale:**
- Better UX (chat still works, just with cheaper model)
- Cost protection while maintaining availability
- User gets response indicating model switch

**Implications:**
- Response includes `modelUsed` field
- UI can optionally display "Using fallback model" message
- Both models must be enabled in Bedrock

**Alternative Rejected:** Hard limit with 429 error (poor UX)

---

### ADR-8: Single Configuration Page in SAM UI

**Decision:** All configuration (OCR + chat) on `/settings` page, conditionally show chat section.

**Rationale:**
- Simpler navigation (one settings page)
- Chat settings only appear if Amplify deployed
- Easier to maintain than separate pages

**Implications:**
- Detection via `chat_deployed` field in ConfigurationTable
- Separate React component files (`OcrSettings.tsx`, `ChatSettings.tsx`)
- Single "Save Configuration" button for both sections

**Alternative Rejected:** Separate `/settings/chat` route (more navigation complexity)

---

### ADR-9: Theme System (Presets + Overrides)

**Decision:** Provide preset themes (light/dark/brand) with optional granular overrides.

**Rationale:**
- Quick setup for non-technical admins (presets)
- Flexibility for advanced customization (overrides)
- Matches common design system patterns

**Implications:**
- Web component applies preset CSS variables first, then overrides
- ConfigurationTable stores both `chat_theme_preset` and `chat_theme_overrides`
- Admin UI shows preset tiles + expandable advanced section

**Alternative Rejected:** CSS variables only (too technical for admins)

---

## Technical Prerequisites

### Knowledge Requirements

Before starting implementation, familiarize yourself with:

1. **Python Patterns in this Codebase:**
   - Read `publish.py` functions: `package_ui_source()`, `sam_deploy()`, `seed_configuration_table()`
   - Note error handling pattern: log with `log_error()`, raise `IOError` with context
   - See validation pattern: `validate_project_name()`, `validate_region()`

2. **SAM Template Structure:**
   - Read `template.yaml` Parameters, Resources, Outputs sections
   - Understand nested stacks pattern (if used)
   - Find existing DynamoDB table definition (ConfigurationTable)

3. **Existing Lambda Patterns:**
   - Review `src/lambda/configuration_resolver/` (if exists)
   - Note AWS SDK client initialization
   - See error handling and logging patterns

4. **React/TypeScript Patterns:**
   - Read existing `src/ui/src/components/` files
   - Note state management approach (Context API, Redux, or props)
   - See how ConfigurationTable is queried from UI

5. **Amplify Gen 2 Basics:**
   - Read `amplify/backend.ts` current structure
   - Understand `defineBackend()`, `defineData()`, `defineAuth()`
   - Review `amplify/data/resource.ts` schema and custom queries

### Tools & Environment

Ensure your environment has:

```bash
# Python
python3 --version  # Should be 3.13+
uv --version       # Package manager

# Node.js
node --version     # Should be 24+
npm --version

# AWS Tools
aws --version
sam --version
npx ampx version   # Amplify Gen 2 CLI

# Docker (for SAM builds)
docker --version
docker ps  # Verify Docker daemon running
```

### Codebase Setup

```bash
# Clone and enter working directory
cd /root/RAGStack-Lambda/.worktrees/deploy-amplify

# Install Python dependencies
uv pip install -r requirements.txt

# Install Node dependencies
npm install

# Verify tests run
npm test
pytest tests/
```

---

## Design Patterns to Follow

### Error Handling

**Match existing Lambda patterns:**

```python
# Example from existing codebase
try:
    result = some_operation()
    log_success("Operation completed")
except ClientError as e:
    log_error(f"AWS operation failed: {e}")
    raise IOError(f"Descriptive context: {e}") from e
```

**In your implementation:**
- Use existing `log_info()`, `log_success()`, `log_error()` helpers
- Raise `IOError`, `ValueError`, or `FileNotFoundError` with context
- Let caller handle exceptions (don't swallow errors)

### Testing Pattern

**Unit tests only (minimal):**

```python
# test_seed_configuration.py
def test_chat_schema_has_required_fields():
    schema = get_chat_schema()  # Extract logic to test
    assert 'chat_require_auth' in schema['properties']
    assert schema['properties']['chat_require_auth']['default'] is False
```

**What to test:**
- Public function inputs/outputs
- Schema structure validation
- Default values correctness

**What NOT to test:**
- AWS SDK calls (assume they work)
- Integration between components
- End-to-end flows

### Commit Pattern

**Feature-level commits (5-10 per phase):**

```bash
# Good commits
git commit -m "feat(config): extend ConfigurationTable schema with chat fields"
git commit -m "test(config): add chat schema validation tests"
git commit -m "feat(publish): add package_amplify_chat_source function"

# Bad commits (too granular)
git commit -m "add chat_require_auth field"
git commit -m "add chat_primary_model field"
git commit -m "add chat_fallback_model field"
```

**Conventional Commits Scopes:**
- `config` - ConfigurationTable changes
- `publish` - publish.py modifications
- `amplify` - Amplify backend.ts changes
- `component` - Web component (src/amplify-chat)
- `ui` - SAM admin UI changes
- `docs` - Documentation updates

---

## Cross-Phase Contracts

These interfaces must be maintained across phases:

### 1. ConfigurationTable Schema (Phase 1 → Phase 4, 5)

**Contract:**
```python
{
  'Configuration': 'Default',
  'chat_deployed': bool,            # Phase 1 sets, Phase 5 reads
  'chat_require_auth': bool,        # Phase 1 defines, Phase 4 reads
  'chat_primary_model': str,        # Phase 1 defines, Phase 4 reads
  'chat_fallback_model': str,       # Phase 1 defines, Phase 4 reads
  'chat_global_quota_daily': int,   # Phase 1 defines, Phase 4 reads
  'chat_per_user_quota_daily': int, # Phase 1 defines, Phase 4 reads
  'chat_theme_preset': str,         # Phase 1 defines, Phase 5 reads
  'chat_theme_overrides': dict,     # Phase 1 defines, Phase 5 reads
}
```

### 2. amplify/data/config.ts (Phase 3 → Phase 4)

**Contract:**
```typescript
export const KNOWLEDGE_BASE_CONFIG = {
  knowledgeBaseId: string,              // Existing
  region: string,                       // Existing
  configurationTableName: string,       // Phase 3 adds, Phase 4 reads
  webComponentSourceBucket: string,     // Phase 3 adds
  webComponentSourceKey: string,        // Phase 3 adds
} as const;
```

### 3. Amplify Stack Outputs (Phase 3 → publish.py)

**Contract:**
```python
outputs = {
  'WebComponentCDN': 'https://d1234.cloudfront.net/amplify-chat.js',
  'AssetBucketName': 'amplify-stack-assetbucket-abc123',
  'BuildProjectName': 'amplify-stack-webcomponentbuild-xyz',
  'DistributionId': 'E1234567890ABC',
}
```

### 4. Web Component Attributes (Phase 2 → Phase 4)

**Contract:**
```html
<amplify-chat
  conversation-id="string"     <!-- Required -->
  user-id="string"            <!-- Optional, Phase 4 uses for auth -->
  user-token="string"         <!-- Optional, Phase 4 validates -->
  header-text="string"        <!-- Optional -->
  show-sources="boolean"      <!-- Optional -->
></amplify-chat>
```

### 5. Conversation Handler Response (Phase 4 → Web Component)

**Contract:**
```typescript
{
  content: string,              // AI response text
  sources: Source[],            // Document citations
  modelUsed: string,            // Which model answered (primary or fallback)
}
```

---

## File Locations Reference

Quick reference for where to find key files:

```
RAGStack-Lambda/
├── publish.py                          # Deployment orchestration
├── template.yaml                       # SAM CloudFormation template
├── amplify/
│   ├── backend.ts                      # Amplify resources definition
│   ├── data/
│   │   ├── config.ts                   # Auto-generated config (Phase 3)
│   │   └── resource.ts                 # GraphQL schema + custom queries
│   └── auth/resource.ts                # Cognito configuration
├── src/
│   ├── amplify-chat/                   # Web component package (Phase 2)
│   │   ├── package.json
│   │   ├── vite.wc.config.ts
│   │   ├── src/
│   │   │   ├── wc.ts                   # Web component entry
│   │   │   ├── components/
│   │   │   │   ├── AmplifyChat.wc.ts
│   │   │   │   └── ChatWithSources.tsx
│   │   │   └── types/index.ts
│   │   └── tests/
│   ├── lambda/
│   │   └── configuration_resolver/    # Existing config Lambda
│   └── ui/                             # SAM admin UI (Phase 5)
│       └── src/
│           ├── pages/Settings.tsx
│           └── components/
│               ├── OcrSettings.tsx     # Existing
│               └── ChatSettings.tsx    # Phase 5 creates
└── docs/plans/amplify-chat/            # This plan
```

---

## Common Pitfalls to Avoid

1. **Don't modify Phase 0 contracts** - These are locked interfaces between phases
2. **Don't add features not in spec** - YAGNI principle applies strictly
3. **Don't skip unit tests** - Even minimal tests catch regressions
4. **Don't use hardcoded values** - Extract to config or constants
5. **Don't ignore existing patterns** - Match codebase style and error handling
6. **Don't commit broken code** - Each commit should leave codebase in working state
7. **Don't bundle node_modules** - Exclude from zip files (CodeBuild installs fresh)

---

## Next Steps

Once you've read and understood this Phase 0:

1. ✅ Verify your environment meets prerequisites
2. ✅ Read through existing codebase files listed in "File Locations Reference"
3. ✅ Understand the ADRs and cross-phase contracts
4. ✅ Proceed to [Phase-1.md](Phase-1.md)

---

**Questions?** Review the ADRs above for architectural rationale. If unclear, refer to existing codebase patterns.
