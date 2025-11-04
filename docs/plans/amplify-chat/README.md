# Amplify Chat Implementation Plan

**Feature:** Optional Amplify chat component deployment with CDN distribution, runtime configuration, and cost controls.

## Overview

This plan implements an embeddable AI chat web component that integrates with the existing RAGStack-Lambda SAM deployment. The chat component queries the Bedrock Knowledge Base via Amplify backend, with optional authentication, configurable rate limits, and automatic model degradation for cost protection.

## Key Features

- ✅ Optional deployment via `--deploy-chat` flag (defaults to enabled)
- ✅ Web component distributed via CloudFront CDN
- ✅ Runtime configuration via SAM admin UI (no redeployment needed)
- ✅ Optional authentication (anonymous or token-based)
- ✅ Rate limiting with automatic model degradation (cost protection)
- ✅ Theme customization (presets + granular overrides)

## Architecture

**Two-Stack Design:**
1. **SAM Stack** (RAGStack-{project}) - Owns document processing backend, Knowledge Base, admin UI, ConfigurationTable
2. **Amplify Stack** (amplify-{project}-{branch}) - Owns chat GraphQL API, Lambda, Cognito, web component CDN

**Integration Points:**
- SAM ConfigurationTable ← Read by Amplify Lambda (runtime config)
- SAM Knowledge Base ← Queried by Amplify conversation handler
- Amplify CDN → Outputs web component URL for embedding

## Prerequisites

Before starting any phase:

1. **Environment Setup:**
   - Python 3.13+, Node.js 24+
   - AWS CLI configured with admin credentials
   - SAM CLI installed
   - Docker running (for SAM builds)

2. **Codebase Familiarity:**
   - Read existing `publish.py` deployment flow
   - Review `src/ui/` React application structure
   - Understand `template.yaml` SAM resources
   - Review existing Lambda functions in `src/lambda/`

3. **Testing Tools:**
   - pytest installed (`uv pip install pytest pytest-cov`)
   - Node test runner (`npm test` in project root)

## Phase Summary

| Phase | Engineer Focus | Deliverable | Dependencies |
|-------|---------------|-------------|--------------|
| [Phase 0](Phase-0.md) | Prerequisites | ADRs, design decisions, environment setup | None |
| [Phase 1](Phase-1.md) | SAM Backend | ConfigurationTable schema, publish.py packaging | Phase 0 |
| [Phase 2](Phase-2.md) | Web Component | React component, build pipeline, bundling | Phase 1 |
| [Phase 3](Phase-3.md) | Amplify Infra | CDN resources, CodeBuild, deployment automation | Phase 1, 2 |
| [Phase 4](Phase-4.md) | Amplify Backend | Conversation handler, config reading, rate limits | Phase 3 |
| [Phase 5](Phase-5.md) | SAM UI | Admin configuration interface | Phase 4 |

## Navigation

- **Start here:** [Phase-0.md](Phase-0.md) - Read ADRs and design decisions
- **Sequential implementation:** Complete phases 1→2→3→4→5 in order
- **Each phase is self-contained:** All context, instructions, and verification steps included

## Development Principles

This implementation follows:

- **DRY (Don't Repeat Yourself)** - Extract shared logic, avoid duplication
- **YAGNI (You Aren't Gonna Need It)** - Implement only what's specified, no extras
- **TDD (Test-Driven Development)** - Write unit tests for business logic
- **Atomic commits** - Feature-level commits with conventional commit messages
- **Match existing patterns** - Follow error handling, logging, and code style from existing codebase

## Commit Message Format

Use conventional commits format:

```
feat(scope): add feature description
test(scope): add test description
fix(scope): fix bug description
refactor(scope): refactor description
docs(scope): documentation update
```

Examples:
- `feat(config): extend ConfigurationTable schema with chat fields`
- `test(config): add seed_configuration_table chat field tests`
- `feat(amplify): add CDN resources to backend.ts`

## Getting Help

- **Existing code patterns:** Search codebase for similar implementations
- **AWS SDK examples:** Check AWS documentation for Boto3/CDK usage
- **Phase questions:** Each phase includes "Common Issues" section
- **Design rationale:** See Phase-0.md ADRs for architectural decisions

## Verification

At the end of Phase 5, you should be able to:

1. Deploy with: `python publish.py --project-name test --admin-email admin@example.com --region us-east-1 --deploy-chat`
2. See CDN URL in deployment outputs
3. Embed chat: `<script src="https://CDN_URL/amplify-chat.js"></script><amplify-chat></amplify-chat>`
4. Configure chat settings in SAM admin UI at `/settings`
5. Observe automatic model degradation when quotas exceeded

---

**Ready to start?** → [Phase-0.md](Phase-0.md)
