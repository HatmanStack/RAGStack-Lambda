# Implementation Plan: Settings UI & Chat Feature

## Overview

This implementation plan guides the development of two major features for RAGStack-Lambda:

1. **Settings UI Enhancement** - Add OCR backend selection and chat model configuration
2. **Knowledge Base Chat** - Conversational interface for querying documents

The plan is organized into 4 sequential phases, with each phase building on previous work. Each phase follows Test-Driven Development (TDD) principles with comprehensive test coverage.

## Target Audience

This plan is designed for a skilled engineer who:
- Has strong development skills but zero context on this codebase
- May be unfamiliar with the toolset and problem domain
- Will follow instructions precisely
- Understands TDD, DRY, and YAGNI principles

## Prerequisites

Before starting Phase 1, ensure:

✅ **Environment Setup**:
- Repository cloned and in working state
- Python environment managed by `uv` using `.venv` in working tree
- All dependencies installed (`npm install` for UI, `uv` managed Python packages)
- SAM CLI configured and tested (`sam build` works)
- Can run `sam local invoke` successfully
- Can run `cd src/ui && npm start` successfully

✅ **Knowledge**:
- Read `CLAUDE.md` in project root (understand project structure)
- Familiar with AWS SAM, Lambda, AppSync, DynamoDB
- Comfortable with React 19, CloudScape Design System
- Understand GraphQL and AWS Amplify v6

✅ **Tools**:
- Git configured with default credentials
- Code editor set up (VS Code recommended)
- Access to `.claude/` subagents for referencing base repository patterns

## Phase Summary

| Phase | Description | Est. Tokens | Duration |
|-------|-------------|-------------|----------|
| [Phase 0](Phase-0.md) | ADRs, Design Decisions, Prerequisites | ~15k | 1 hour |
| [Phase 1](Phase-1.md) | Settings Backend (Schema + GraphQL) | ~25k | 1 day |
| [Phase 2](Phase-2.md) | Settings Frontend (UI Rendering) | ~20k | 1 day |
| [Phase 3](Phase-3.md) | Chat Backend (QueryKB Enhancement) | ~30k | 1.5 days |
| [Phase 4](Phase-4.md) | Chat Frontend (Chat UI Components) | ~35k | 1.5 days |
| **Total** | | **~125k** | **~5.5 days** |

## Development Principles

### Test-Driven Development (TDD)
- **Write tests FIRST**, then implement
- Aim for 80%+ code coverage
- Tests serve as living documentation
- Red → Green → Refactor cycle

### DRY (Don't Repeat Yourself)
- Extract common patterns into shared utilities
- Reuse existing components and hooks
- Reference base repository patterns via subagents

### YAGNI (You Aren't Gonna Need It)
- Implement only what's specified in the plan
- No premature optimization or feature creep
- Happy path + critical errors only

### Commit Strategy
- **Feature commits**: One commit per complete feature with tests
- **Conventional commits format**: `feat(scope): description` or `test(scope): description`
- **Atomic**: Each commit should be deployable (tests pass)
- Expected ~2-3 commits per phase

## Verification Strategy

### Local Development Only
- ✅ Use `sam local invoke` for Lambda testing
- ✅ Use `sam local start-api` for API Gateway simulation
- ✅ Use `npm start` for frontend development
- ❌ **DO NOT deploy to AWS** during implementation
- ❌ **DO NOT run CloudFormation updates**

### Testing Layers
1. **Unit Tests**: Individual functions and components
2. **Integration Tests**: GraphQL resolvers, API interactions
3. **Manual Tests**: UI workflows and user experience

## Navigation

Start with **[Phase 0: Prerequisites & ADRs](Phase-0.md)** to understand design decisions before implementation.

### Phase Files
- **[Phase 0: Prerequisites & ADRs](Phase-0.md)** - Read this FIRST
- **[Phase 1: Settings Backend](Phase-1.md)** - Configuration schema and GraphQL
- **[Phase 2: Settings Frontend](Phase-2.md)** - Settings UI rendering
- **[Phase 3: Chat Backend](Phase-3.md)** - QueryKB Lambda enhancement
- **[Phase 4: Chat Frontend](Phase-4.md)** - Chat interface components

## Subagent Reference

Use these subagents to find patterns from the base repository:

- **explore-base-general** - Project structure, general patterns
- **explore-base-architecture** - Lambda patterns, code organization
- **explore-base-infrastructure** - SAM template patterns, CloudFormation
- **config-pattern-finder** - Configuration management patterns
- **explore-base-testing** - Test organization and patterns

Access via: Request Claude to "Use [agent-name] to find [pattern]"

See `.claude/SUBAGENTS_USAGE.md` for detailed guidance.

## Important Notes

### Git and Version Control
- **Commit frequently** with descriptive messages
- Use conventional commits: `feat:`, `test:`, `fix:`, `refactor:`, `docs:`
- Each commit should pass all tests
- This plan directory (`docs/plans/`) is git-ignored

### Error Handling
- Focus on happy path + critical errors
- Graceful degradation when configuration unavailable
- User-friendly error messages
- Basic logging for debugging

### Documentation
- Docstrings for public APIs and complex functions
- Comments only where logic is non-obvious
- No extensive README updates (CLAUDE.md covers it)
- ADRs capture architectural decisions

## Getting Help

If you get stuck:

1. **Reference Phase 0** for architectural context
2. **Use subagents** to find patterns in base repository
3. **Check test files** to understand expected behavior
4. **Review CLAUDE.md** for project conventions
5. **Ask questions** if requirements are ambiguous

## Success Criteria

By the end of Phase 4, you should have:

✅ Settings page with 7 configuration fields (OCR + Chat + Embedding)
✅ Conditional field rendering (Bedrock model only when Bedrock selected)
✅ Re-embedding workflow preserved and tested
✅ Chat page at `/chat` route with conversational interface
✅ Session-based conversation history via Bedrock
✅ Source citations displayed for chat responses
✅ 80%+ test coverage for all new code
✅ All tests passing locally
✅ Clean commit history with conventional commits

## Let's Begin!

Start with **[Phase 0: Prerequisites & ADRs](Phase-0.md)** →
