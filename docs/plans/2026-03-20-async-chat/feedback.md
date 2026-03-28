# Feedback: Async Chat Query

## Active Feedback

<!-- No active feedback items -->

## Resolved Feedback

### PLAN_REVIEW-001: Resolver function receives arguments dict, not full event
- **Source:** Plan Reviewer
- **Phase:** 1
- **Resolution:** Revised Phase 1 Task 2 to change the resolver signature from `query_knowledge_base(event)` to `query_knowledge_base(args)`, matching the existing routing pattern at line 292 where `resolver(event["arguments"])` is called. All argument extraction now uses `args["query"]` etc. instead of `event["arguments"]["query"]`. Identity is handled via `_current_identity` module-level variable (see PLAN_REVIEW-003). Public access is handled via `access_requirements` dict (see PLAN_REVIEW-002). Also fixed Task 3 `get_conversation` to accept `args` instead of `event`.

### PLAN_REVIEW-002: check_public_access pattern inconsistency
- **Source:** Plan Reviewer
- **Phase:** 1
- **Resolution:** Revised Phase 1 Task 2 to add `"queryKnowledgeBase": "chat"` to the `access_requirements` dict in `lambda_handler` (new step 3), following the existing pattern. Removed step (e) that called `check_public_access` inside the resolver. The resolver no longer needs access to the full event for public access checks.

### PLAN_REVIEW-003: Forwarding identity to async Lambda invocation
- **Source:** Plan Reviewer
- **Phase:** 1
- **Resolution:** Revised Phase 1 Task 2 to add a `_current_identity` module-level variable (new step 4). `lambda_handler` sets this variable from `event.get("identity")` before calling the resolver. The resolver reads `_current_identity` when building the async invoke payload. This is safe because Lambda processes one request at a time per container. Verification checklist updated to confirm this pattern.

### PLAN_REVIEW-004: MessageList.test.tsx referenced in Phase 2 Task 3 but tests deferred
- **Source:** Plan Reviewer
- **Phase:** 2
- **Resolution:** Added a scope note at the top of Phase 2 Task 3 clarifying that it covers only MessageList component tests (slow response indicator), while the broader async flow tests (mutation, polling, timeout, error handling) are covered in Task 4 (ChatInterface tests).

### PLAN_REVIEW-005: Source type fields in GET_CONVERSATION_QUERY may include fields not in ConversationTurn schema
- **Source:** Plan Reviewer
- **Phase:** 2
- **Resolution:** Added a verification checklist item to Phase 2 Task 1 instructing the engineer to verify the `GET_CONVERSATION_QUERY` source selection set includes all fields the UI actually renders, and noting that optional `Source` fields like `thumbnailUrl`, `caption`, `segmentIndex` can be omitted if unused.

### PLAN_REVIEW-006: conversationId lifecycle change not fully addressed
- **Source:** Plan Reviewer
- **Phase:** 2
- **Resolution:** No plan changes needed. As the reviewer noted, the existing code already receives `conversationId` as a prop, and the plan correctly does not change this behavior. ADR-6's "client generates conversationId on first message" is already handled by the existing prop pattern.
