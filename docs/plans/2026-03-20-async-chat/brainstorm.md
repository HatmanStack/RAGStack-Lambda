# Feature: Async Chat Query (Mutation + Polling)

## Overview

Convert `queryKnowledgeBase` from a synchronous GraphQL query to an async mutation + polling pattern to bypass AppSync's 30-second Lambda resolver timeout. The current bottleneck is the Bedrock Converse API (Claude Sonnet 4.6) which takes 30-50s for detailed responses, exceeding AppSync's hard 30s resolver limit despite the Lambda's 90s timeout.

The new flow: client sends a `queryKnowledgeBase` mutation that returns immediately with a request acknowledgment. The AppSync resolver async-invokes the existing `QueryKBFunction` Lambda, which runs the full pipeline (filter generation, multislice retrieval, Converse API, source extraction) and writes the result to the existing `ConversationHistoryTable`. The client polls a new `getConversation` query every 2-3s to check for the response, correlating via `requestId`. This approach keeps the ragstack-chat web component dependency-free (no WebSocket/Amplify needed) and follows established async invocation patterns already used throughout the codebase.

The `getConversation` query is intentionally broader than what polling strictly requires — it returns the full conversation, which positions it for future conversation listing and search features without requiring schema changes later.

## Decisions

1. **Async mechanism: Lambda self-invocation** — `appsync_resolvers/index.py` validates input and calls `lambda_client.invoke(InvocationType='Event')` on `QueryKBFunction`. Matches the existing pattern used for image processing, KB ingestion, and batch processing throughout the codebase. Step Functions and SQS rejected as overkill for a single-step operation.
2. **Two-function split** — The AppSync resolver (in `appsync_resolvers/index.py`) handles the mutation, validates input, and async-invokes the existing `QueryKBFunction`. The query_kb handler stays mostly unchanged. Matches existing pattern where resolvers invoke separate Lambdas.
3. **Polling over WebSocket subscriptions** — The ragstack-chat web component has zero runtime dependencies. Implementing AppSync realtime WebSocket protocol (IAM SigV4 WSS handshake, keep-alive, reconnection) would be disproportionate complexity for a "send one message, get one response" interaction. Polling 10-15 lightweight DynamoDB reads over 30-50s is trivial. WebSocket is better suited for token-streaming, which is not in scope.
4. **Error handling: errors in DynamoDB + client timeout** — Async Lambda catches errors and writes them to `ConversationHistoryTable` (client sees them via polling). Client also has a progressive timeout as a safety net for Lambda crashes. No subscription-based error delivery needed since we chose polling.
5. **Progressive client timeout** — 30s normal state, then "taking longer than usual" indicator, 90s hard timeout. Keeps user informed without cutting off legitimate slow responses.
6. **New distinct schema types** — `ChatRequest` (mutation response) and `ChatResult` (in conversation data) as separate types from the existing `ChatResponse`. Clean separation between the async contract and the legacy sync shape.
7. **Replace sync query entirely** — No backward compatibility path. The sync `queryKnowledgeBase` query is removed and replaced with the mutation. Nothing outside the dashboard and ragstack-chat calls this API.
8. **Store results in existing `ConversationHistoryTable`** — No new DynamoDB table. The query_kb handler already writes conversation history here; the polling query reads from the same table. Request status is implicit: if the response record exists for the requestId, it's done.
9. **conversationId as primary, requestId as correlation** — `conversationId` is the durable entity (subscription filter, future listing/search key). `requestId` is per-message correlation so the client knows which response matches which sent message. Client generates both IDs (UUID) — conversationId on first message, reused for subsequent turns; requestId per message.
10. **`getConversation` query for polling** — Returns full conversation history for a conversationId. Client polls this and checks for a response matching its requestId. Broader than strictly needed for polling, but directly reusable for future conversation listing/search without schema changes.
11. **No future-proofing for conversation listing** — No new GSIs, no title generation, no search infrastructure. The `getConversation` query is the only concession to future needs, and it's useful for polling regardless.

## Scope: In

- New `queryKnowledgeBase` mutation in GraphQL schema (replaces sync query)
- New `ChatRequest` and `ChatResult` schema types
- New `getConversation(conversationId: ID!)` query and resolver
- Mutation resolver in `appsync_resolvers/index.py` — validates input, async-invokes QueryKBFunction
- `query_kb/handler.py` changes — write result (success or error) to ConversationHistoryTable, publish via `execute_appsync_mutation`
- `getConversation` resolver — lightweight DynamoDB read from ConversationHistoryTable
- `template.yaml` changes — new resolver/datasource wiring, schema updates, IAM permissions for async invoke
- `ChatInterface.tsx` changes — send mutation, poll `getConversation`, correlate via requestId
- Progressive timeout UI states in ragstack-chat (30s / "still working" / 90s)
- Remove old sync `queryKnowledgeBase` query and resolver

## Scope: Out

- WebSocket/subscription implementation in ragstack-chat
- Amplify or any new runtime dependency in ragstack-chat
- Conversation listing/search UI
- DynamoDB GSI changes or new tables
- Conversation title generation
- Token-by-token streaming
- Request status tracking beyond implicit "response exists in DynamoDB"
- Backward compatibility with sync query
- Dashboard UI (`src/ui/`) subscription changes for chat (dashboard uses ragstack-chat component, inherits the polling behavior)

## Open Questions

- **ConversationHistoryTable schema compatibility** — The planner should verify the existing table schema (partition key, sort key, attributes) can accommodate a requestId-correlated record without breaking existing conversation history reads. May need a sort key scheme like `conversationId#requestId` or a status attribute.
- **Concurrent messages** — If a user sends a second message before the first response arrives, both will be polling. The `getConversation` query returns the full conversation, so both responses will appear. The planner should decide whether to block concurrent sends in the UI or handle gracefully.
- **Polling interval tuning** — 2-3s is a starting assumption. The planner should consider whether to use exponential backoff or a fixed interval given the known 30-50s typical response time.
- **API key auth in ragstack-chat** — The component currently uses `SAM_GRAPHQL_API_KEY` for some paths and IAM for others. The new mutation and polling query need to work with whichever auth mode ragstack-chat uses. Planner should verify resolver auth directives.

## Relevant Codebase Context

- `src/lambda/appsync_resolvers/index.py` — Existing mutation resolvers, `lambda_client.invoke(InvocationType='Event')` pattern at lines 837, 1341, 2350
- `src/lambda/query_kb/handler.py` — Full query pipeline (lines 201-709), 90s timeout, 1769MB memory
- `lib/ragstack_common/appsync.py` — `execute_appsync_mutation()` for publishing results back to AppSync
- `src/api/schema.graphql` — Current schema, `queryKnowledgeBase` query at line 13, subscription patterns for document/scrape/image/reindex
- `src/ragstack-chat/src/components/ChatInterface.tsx` — Current sync HTTP POST implementation, `iamFetch` utility
- `src/ragstack-chat/src/utils/iamAuth.ts` — IAM SigV4 signing for HTTP requests (reusable for mutation + polling calls)
- `src/ui/src/hooks/useDocuments.ts` — Amplify subscription pattern (reference only, not used in ragstack-chat)
- `template.yaml` lines 1703-1757 — QueryKBFunction definition; lines 3450-3467 — resolver wiring; lines 3287-3295 — datasources
- `template.yaml` ConversationHistoryTable — existing DynamoDB table for conversation storage
- `src/ragstack-chat/src/amplify-config.template.ts` — Build-time config injection for API endpoint/key

## Technical Constraints

- **AppSync 30s resolver timeout** — The hard limit driving this entire change. Not configurable.
- **Lambda 90s timeout on QueryKBFunction** — Sufficient for Bedrock Converse API, no change needed.
- **ragstack-chat is a zero-dependency web component** — No Amplify, no AWS SDK at runtime. All AWS interaction goes through `iamAuth.ts` utility. New polling logic must stay within this constraint.
- **IAM auth for mutations** — `execute_appsync_mutation` in appsync.py uses IAM SigV4 signing. The new `publishChatResult`-equivalent (writing to DynamoDB instead) needs appropriate IAM permissions on the QueryKBFunction role.
- **API key auth for ragstack-chat** — The web component uses API key auth (`SAM_GRAPHQL_API_KEY`). New mutation and query resolvers need `@aws_api_key` directives or equivalent.
- **Docker required for Lambda layer builds** — Any changes to `lib/ragstack_common/` require Docker for SAM build.
