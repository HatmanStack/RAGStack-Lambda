# Phase 0: Prerequisites & Architectural Decisions

## Overview

This phase documents the architectural decisions and design rationale for the Settings UI and Chat feature implementation. Read this before starting implementation to understand the "why" behind technical choices.

**Estimated Reading Time**: 30 minutes

## Table of Contents

1. [Architectural Decision Records (ADRs)](#architectural-decision-records-adrs)
2. [Feature Design Summary](#feature-design-summary)
3. [Technical Approach](#technical-approach)
4. [Testing Strategy](#testing-strategy)
5. [Prerequisites Checklist](#prerequisites-checklist)

---

## Architectural Decision Records (ADRs)

### ADR-001: Configuration Storage Strategy

**Decision**: Use existing DynamoDB-backed configuration table with schema-driven UI rendering

**Context**:
- RAGStack-Lambda already has a configuration system in `lib/ragstack_common/config.py`
- DynamoDB table stores Schema (JSON), Default (JSON), and Custom (JSON)
- Frontend Settings page renders fields dynamically from schema

**Alternatives Considered**:
1. Environment variables in SAM template - Rejected (requires redeployment for changes)
2. SSM Parameter Store - Rejected (more complex, less flexible)
3. Hardcoded in Lambda functions - Rejected (not user-configurable)

**Consequences**:
- ✅ Runtime configuration changes without redeployment
- ✅ Schema-driven UI automatically adapts to new fields
- ✅ Existing infrastructure reused (DRY principle)
- ⚠️ Configuration changes take effect on next Lambda invocation (acceptable latency)

---

### ADR-002: Chat Implementation Approach

**Decision**: Enhance existing QueryKB Lambda with session support (Knowledge Base chat) instead of implementing document-specific chat

**Context**:
- Base repository has TWO chat features:
  1. Document chat (loads full document, uses prompt caching)
  2. Knowledge Base query (vector search across documents)
- RAGStack-Lambda's core value is the Knowledge Base pipeline (OCR → embeddings → KB)

**Alternatives Considered**:
1. Copy document chat from base repo - Rejected (complex, not aligned with KB use case)
2. Implement both features - Rejected (YAGNI, too much scope)
3. Build entirely new chat system - Rejected (reinventing wheel)

**Consequences**:
- ✅ Simple implementation (add sessionId parameter)
- ✅ Leverages existing Knowledge Base infrastructure
- ✅ Bedrock manages conversation history automatically
- ✅ Cross-document search (main use case)
- ✅ Lower cost (chunk tokens vs full document)
- ❌ Cannot do deep dives into specific single documents (acceptable trade-off)

---

### ADR-003: Model Configuration Strategy

**Decision**: Make chat model user-configurable via Settings UI, read dynamically from configuration table

**Context**:
- Different models have different cost/quality trade-offs
- Users may want Nova Lite (cheap) for dev, Claude Sonnet (quality) for prod
- Model selection should not require code changes

**Alternatives Considered**:
1. Hardcode model in Lambda - Rejected (not flexible)
2. Environment variable in SAM template - Rejected (requires redeployment)
3. Different Lambda functions per model - Rejected (code duplication)

**Consequences**:
- ✅ Users can switch models without redeployment
- ✅ Cost optimization based on use case
- ✅ Consistent with embedding model configuration pattern
- ⚠️ Model change takes effect on next Lambda invocation (acceptable)

---

### ADR-004: Test Strategy

**Decision**: Comprehensive TDD with 80%+ coverage, test-first approach

**Context**:
- Engineer is unfamiliar with codebase
- Tests serve as living documentation
- High coverage catches regressions early

**Alternatives Considered**:
1. Minimal testing (manual only) - Rejected (risky, hard to refactor)
2. Test-after approach - Rejected (misses TDD benefits)
3. 100% coverage requirement - Rejected (diminishing returns)

**Consequences**:
- ✅ Tests guide implementation (clear requirements)
- ✅ Confidence in refactoring
- ✅ Documentation of expected behavior
- ⚠️ Slower initial development (acceptable for quality)

---

### ADR-005: Local Development Only

**Decision**: All verification done locally (SAM local + npm start), no AWS deployments during implementation

**Context**:
- AWS deployments are slow (~5-10 minutes)
- Deployment costs during development
- Local testing is sufficient for verification

**Alternatives Considered**:
1. Deploy after each phase - Rejected (slow, expensive)
2. Continuous deployment - Rejected (requires CI/CD setup)
3. Deploy only at milestones - Rejected (may miss issues)

**Consequences**:
- ✅ Faster iteration cycle
- ✅ No AWS costs during development
- ✅ Cleaner dev environment
- ⚠️ Integration issues caught later (acceptable, thorough local testing mitigates)

---

## Feature Design Summary

### Settings Enhancement

**Goal**: Add 3 new configuration fields to Settings page

**New Fields**:
1. **ocr_backend** - Dropdown: Textract or Bedrock
2. **bedrock_ocr_model_id** - Dropdown: Claude models (conditional, only visible when Bedrock selected)
3. **chat_model_id** - Dropdown: Nova/Claude models for KB queries

**Existing Fields** (preserve):
4. **text_embed_model_id** - Text embedding model
5. **image_embed_model_id** - Image embedding model

**Critical Feature**: Re-embedding workflow (warn users when embedding models change, offer to regenerate embeddings)

**UI Pattern**: Schema-driven rendering (backend defines fields, frontend renders dynamically)

---

### Knowledge Base Chat

**Goal**: Add conversational chat interface for querying Knowledge Base

**Key Features**:
1. **Dedicated `/chat` route** - New page in main navigation
2. **Session-based history** - Bedrock manages conversation context via sessionId
3. **Source citations** - Display which documents contributed to answer
4. **Message bubbles** - User (blue, right) vs AI (gray, left)
5. **New conversation** - Button to reset session and start fresh

**Backend**: Enhance existing QueryKB Lambda to accept optional sessionId parameter

**Cost**: ~$0.0005 - $0.0120 per query depending on model selected in Settings

---

## Technical Approach

### Backend Architecture

**Configuration Management**:
```
User changes Settings → Frontend calls updateConfiguration mutation
→ AppSync resolver updates DynamoDB Configuration table
→ Next QueryKB invocation reads from ConfigurationManager
→ Effective config = Custom overrides Default
```

**Chat Flow**:
```
User sends message → Frontend calls queryKnowledgeBase with optional sessionId
→ QueryKB Lambda loads chat_model_id from config
→ Calls Bedrock retrieve_and_generate with model ARN and sessionId
→ Bedrock returns answer + new/same sessionId + citations
→ Frontend displays message + stores sessionId for next message
```

**Data Flow**:
```
DynamoDB Config Table
  ├─ Schema: Field definitions (type, enum, description, order, dependsOn)
  ├─ Default: System defaults
  └─ Custom: User overrides

QueryKB Lambda reads via ConfigurationManager
  ├─ Merges Custom → Default
  ├─ Gets chat_model_id
  ├─ Builds Bedrock model ARN
  └─ Invokes retrieve_and_generate API
```

### Frontend Architecture

**Settings Page** (existing, minimal changes):
- Schema-driven field rendering (`renderField` function)
- Conditional visibility (`dependsOn` support)
- Re-embedding workflow modal
- Form state management with React hooks

**Chat Page** (new):
- Main page: `src/ui/src/components/Chat/index.jsx`
- Chat panel: `src/ui/src/components/Chat/ChatPanel.jsx`
- Message bubbles: `src/ui/src/components/Chat/MessageBubble.jsx`
- Source list: `src/ui/src/components/Chat/SourceList.jsx`
- Styling: `src/ui/src/components/Chat/ChatPanel.css`

**State Management**:
```
ChatPanel Component State:
  ├─ messages: Array of {type, content, sources, timestamp}
  ├─ inputValue: Current text input
  ├─ isLoading: Boolean for loading state
  ├─ error: Error message string or null
  └─ sessionId: Current Bedrock session ID or null
```

### GraphQL Schema Updates

**Enhanced Query**:
```graphql
type Query {
  queryKnowledgeBase(
    query: String!
    sessionId: String  # NEW - optional for conversation continuity
  ): ChatResponse    # UPDATED type
}

type ChatResponse {
  answer: String!
  sessionId: String!  # NEW - returned for next message
  sources: [Source!]! # NEW - source citations
  error: String       # NEW - optional error message
}

type Source {
  documentId: String!
  pageNumber: Int
  s3Uri: String!
  snippet: String
}
```

---

## Testing Strategy

### Test Layers

**1. Unit Tests** (~60% of tests):
- Individual functions (extract_sources, get_effective_config)
- React components (MessageBubble, SourceList)
- Utility functions

**2. Integration Tests** (~30% of tests):
- GraphQL resolver end-to-end
- Configuration loading and merging
- ChatPanel with mocked GraphQL

**3. Manual Tests** (~10% of tests):
- UI workflows and user experience
- Conditional field visibility
- Error handling edge cases

### Test Organization

```
lib/ragstack_common/
  └─ test_config.py           # ConfigurationManager unit tests

src/lambda/query_kb/
  └─ test_handler.py          # QueryKB Lambda integration tests

src/ui/src/components/
  ├─ Settings/
  │   └─ Settings.test.jsx    # Settings component tests
  └─ Chat/
      ├─ ChatPanel.test.jsx   # Chat panel integration tests
      ├─ MessageBubble.test.jsx
      └─ SourceList.test.jsx
```

### TDD Workflow

For each feature:
1. **Red**: Write failing test first
2. **Green**: Implement minimum code to pass
3. **Refactor**: Clean up while keeping tests green
4. **Commit**: Feature + tests together

---

## Prerequisites Checklist

Before starting Phase 1, verify:

### Environment

- [ ] Repository cloned to working directory
- [ ] Python managed by `uv` with `.venv` in working tree
- [ ] Run `uv sync` or equivalent to install Python dependencies
- [ ] Run `cd src/ui && npm install` to install frontend dependencies
- [ ] Run `sam build` successfully (Lambda functions compile)
- [ ] Run `sam local invoke ProcessDocumentFunction --help` (SAM CLI works)
- [ ] Run `cd src/ui && npm start` (dev server starts)

### Knowledge

- [ ] Read `CLAUDE.md` in project root (understand project structure)
- [ ] Understand AWS SAM, Lambda, DynamoDB basics
- [ ] Familiar with React 19 and hooks
- [ ] Understand CloudScape Design System components
- [ ] Know GraphQL query/mutation syntax

### Tools

- [ ] Git configured (`git config user.name` and `user.email` set)
- [ ] Code editor installed (VS Code recommended)
- [ ] Can access `.claude/` directory (subagents for base repo reference)
- [ ] Terminal/shell ready for running commands

### Validation

Run these commands to verify readiness:

```bash
# Python environment
python --version  # Should show Python 3.13+

# Node environment
node --version   # Should show Node.js 24+
npm --version    # Should show npm 10+

# SAM CLI
sam --version    # Should show SAM CLI 1.100.0+

# Build test
sam build        # Should complete without errors

# Git test
git status       # Should show clean working tree or expected changes
```

---

## Key Files Reference

You'll be working with these files across all phases:

### Backend Files

**Configuration**:
- `lib/ragstack_common/config.py` - ConfigurationManager (read-only)
- Backend schema updates happen in GraphQL resolver

**Lambda**:
- `src/lambda/query_kb/index.py` - QueryKB handler (enhance in Phase 3)
- `src/lambda/appsync_resolvers/index.py` - GraphQL routing

**GraphQL**:
- `src/api/schema.graphql` - API schema (update in Phase 1 & 3)

### Frontend Files

**Settings** (modify in Phase 2):
- `src/ui/src/components/Settings/index.jsx` - Settings page (existing)

**Chat** (create in Phase 4):
- `src/ui/src/components/Chat/index.jsx` - Main chat page
- `src/ui/src/components/Chat/ChatPanel.jsx` - Chat interface
- `src/ui/src/components/Chat/MessageBubble.jsx` - Message display
- `src/ui/src/components/Chat/SourceList.jsx` - Citation sources
- `src/ui/src/components/Chat/ChatPanel.css` - Styling

**Routing**:
- `src/ui/src/App.jsx` - Add /chat route
- `src/ui/src/components/Layout/Navigation.jsx` - Add chat link

**GraphQL**:
- `src/ui/src/graphql/queries/queryKnowledgeBase.js` - Update query

---

## Subagent Usage Guidance

Throughout implementation, use these subagents to find patterns:

### When to Use Which Agent

**explore-base-general**:
- Need project structure overview
- Looking for general code patterns
- Understanding cross-cutting concerns

**Example**: "Use explore-base-general to show how the base repository organizes Lambda functions"

**explore-base-architecture**:
- Lambda function structure
- Handler patterns
- Error handling approaches

**Example**: "Use explore-base-architecture to find error handling patterns in Lambda functions"

**config-pattern-finder**:
- ConfigurationManager usage
- DynamoDB operations
- GraphQL resolver patterns
- Dynamic form rendering

**Example**: "Use config-pattern-finder to show how ConfigurationManager.get_effective_config() works"

**explore-base-infrastructure**:
- SAM template patterns
- CloudFormation resource definitions
- IAM policies
- Environment variables

**Example**: "Use explore-base-infrastructure to find DynamoDB table definitions in SAM template"

**explore-base-testing**:
- Test organization
- Pytest patterns
- Vitest setup
- Fixture examples

**Example**: "Use explore-base-testing to find pytest fixture patterns for Lambda testing"

### Subagent Best Practices

1. **Be specific** in your requests
2. **State your context** (what you're implementing)
3. **Ask for adaptations** to RAGStack-Lambda
4. **Reference by name** explicitly

See `.claude/SUBAGENTS_USAGE.md` for full documentation.

---

## Design Principles Recap

As you implement, remember:

### DRY (Don't Repeat Yourself)
- Reuse existing ConfigurationManager
- Reuse existing Settings renderField logic
- Copy patterns from base repo, don't reinvent

### YAGNI (You Aren't Gonna Need It)
- Implement only the 7 configuration fields specified
- Happy path + critical errors only
- No premature optimization

### TDD (Test-Driven Development)
- Write tests first, always
- Red → Green → Refactor
- 80%+ coverage target

### Commit Hygiene
- Feature commits (complete feature + tests)
- Conventional commits format
- Descriptive messages

---

## Success Criteria

After reading Phase 0, you should understand:

- [x] Why we're enhancing Settings (runtime configurability)
- [x] Why we chose KB chat over document chat (aligned with RAGStack value)
- [x] Why models are user-configurable (cost optimization)
- [x] Why TDD with high coverage (quality and documentation)
- [x] Why local-only development (speed and cost)
- [x] How configuration flows through the system
- [x] How chat sessions work with Bedrock
- [x] Where to find patterns using subagents
- [x] What files you'll be modifying

---

## Next Steps

Ready to start implementation?

→ **[Continue to Phase 1: Settings Backend](Phase-1.md)**

This phase will add the new configuration fields to the schema and update GraphQL resolvers.

---

**Estimated Reading Time**: 30 minutes
**Estimated Token Count**: ~15,000 tokens
