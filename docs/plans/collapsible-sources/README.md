# Collapsible Sources with Document Access

## Feature Overview

This feature enhances the chat component to provide better control over source citations and direct access to original source documents. Currently, sources are always visible and only show vector snippets. The new implementation adds user-controlled source visibility (expandable/collapsible) and provides secure, time-limited links to download original documents from S3, with admin-configurable access control.

The feature follows the existing pattern of runtime configuration (like `chat_require_auth`), adding a new `chat_allow_document_access` toggle that administrators can control via the web UI. When enabled, users see "View Document" links that generate presigned S3 URLs mapping from Bedrock Knowledge Base citations (which reference the OutputBucket) back to the original uploaded files in the InputBucket.

This implementation prioritizes security (presigned URLs with 1-hour expiry, read-only access, admin-controlled), user experience (collapsible UI with smooth animations, clear affordances), and maintainability (following existing patterns, comprehensive testing, clear documentation).

## Prerequisites

**Development Environment:**
- Node.js 24+
- Python 3.13+ with `uv` package manager
- AWS CLI configured with admin access
- SAM CLI installed
- Docker running (for Lambda layer builds)

**Project Setup:**
- Repository cloned and dependencies installed (`npm install`, `uv pip install -r requirements.txt`)
- Existing deployment of RAGStack-Lambda with chat component
- Access to AWS account with permissions for: S3, DynamoDB, Lambda, IAM

**Knowledge Required:**
- TypeScript/React (for frontend)
- Python (for backend Lambda functions)
- AWS SDK v3 (S3 presigned URLs)
- DynamoDB data modeling
- CSS animations and accessibility patterns

## Phase Summary

| Phase | Goal | Token Estimate | Status |
|-------|------|---------------|--------|
| 0 | Foundation & Architecture | 15,000 | Not Started |
| 1 | Backend Implementation | 75,000 | Not Started |
| 2 | Frontend Implementation | 70,000 | Not Started |
| 3 | Testing & Integration | 45,000 | Not Started |
| **Total** | | **~205,000** | |

## Phase Navigation

- [Phase 0: Foundation & Architecture](./Phase-0.md) - Architecture decisions, design patterns, testing strategy
- [Phase 1: Backend Implementation](./Phase-1.md) - DynamoDB config, document mapping, presigned URLs
- [Phase 2: Frontend Implementation](./Phase-2.md) - Collapsible UI, document links, admin configuration
- [Phase 3: Testing & Integration](./Phase-3.md) - Unit tests, integration tests, E2E tests, deployment

## Implementation Timeline

**Estimated Duration:** 3-5 days (assuming full-time focus)

**Critical Path:**
1. Phase 1 must complete before Phase 2 (backend API contract required)
2. Phase 2 can start once Phase 1 Task 1-3 complete (config + basic mapping)
3. Phase 3 runs in parallel with Phase 2 completion (TDD approach)

## Success Criteria

- ✅ Sources are collapsible by default (user controls visibility)
- ✅ Admin can enable/disable document access via web UI
- ✅ When enabled, users can download original documents (not vectors)
- ✅ Presigned URLs are secure (1-hour expiry, read-only)
- ✅ All existing features continue to work
- ✅ 80%+ test coverage on new code
- ✅ Zero performance regression on chat queries
- ✅ Accessible (keyboard navigation, screen readers)

## Post-Implementation

**Documentation Updates:**
- Update CLAUDE.md with new configuration option
- Add to docs/CONFIGURATION.md
- Update docs/AMPLIFY_CHAT.md with new props

**Monitoring:**
- Track presigned URL generation rate (CloudWatch metrics)
- Monitor S3 GetObject requests on InputBucket
- Alert on failed document mappings

**Future Enhancements:**
- Page-level deep linking for PDFs (#page=N)
- Document preview modal (inline viewer)
- Citation highlighting in documents
- Analytics on which sources users access most
