# Async Chat Query (Mutation + Polling)

## Overview

This plan converts the `queryKnowledgeBase` GraphQL operation from a synchronous query to an asynchronous mutation + polling pattern. The current sync approach hits AppSync's hard 30-second resolver timeout when Bedrock Converse API (Claude Sonnet 4.6) takes 30-50s for detailed responses, despite the Lambda's 90s timeout being sufficient.

The new flow: the client sends a `queryKnowledgeBase` mutation that returns immediately with a `requestId`. The AppSync resolver (in `appsync_resolvers/index.py`) validates input and async-invokes the existing `QueryKBFunction` Lambda via `lambda_client.invoke(InvocationType='Event')`. The Lambda runs the full pipeline and writes results to the existing `ConversationHistoryTable`. The client polls a new `getConversation` query every 2-3s to check for the response, correlating via `requestId`.

This approach keeps the ragstack-chat web component dependency-free (no WebSocket/Amplify needed) and follows the async invocation pattern already used throughout the codebase for image processing, KB ingestion, and batch processing.

## Prerequisites

- Python 3.13+ (use `uv` for all Python package management)
- Node.js 24+ (nvm)
- Docker (required if modifying `lib/ragstack_common/` Lambda layer)
- Familiarity with AWS SAM `template.yaml`, AppSync GraphQL, DynamoDB
- Access to the test suite: `npm run test` (backend + frontend)

## Phase Summary

| Phase | Goal | Token Estimate |
|-------|------|----------------|
| 0 | Foundation: Architecture decisions, patterns, testing strategy | ~3,000 |
| 1 | Backend: Schema, resolvers, Lambda changes, SAM template | ~35,000 |
| 2 | Frontend: ragstack-chat polling, progressive timeout, cleanup | ~25,000 |

## Navigation

- [Phase-0.md](Phase-0.md) - Foundation (ADRs, patterns, testing strategy)
- [Phase-1.md](Phase-1.md) - Backend implementation
- [Phase-2.md](Phase-2.md) - Frontend implementation
- [feedback.md](feedback.md) - Review feedback tracking
