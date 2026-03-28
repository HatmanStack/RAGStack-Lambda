# Phase 1: Backend Implementation

## Phase Goal

Implement the backend async chat pattern: update the GraphQL schema, add the mutation resolver in `appsync_resolvers/index.py`, add the `getConversation` query resolver, modify `query_kb/handler.py` to support async invocation, and wire everything in `template.yaml`.

**Success criteria:**
- `queryKnowledgeBase` mutation accepts `query`, `conversationId`, `requestId` and returns `ChatRequest` with acknowledgment
- Mutation async-invokes QueryKBFunction which writes result to ConversationHistoryTable
- `getConversation` query returns full conversation with status per turn
- Old sync `queryKnowledgeBase` query is removed
- All existing Python tests pass, new tests cover the async flow

**Estimated tokens:** ~35,000

## Prerequisites

- No prior phases required (Phase 0 is reference only)
- Codebase at `main` branch, clean working tree
- `uv` available for Python package management

---

## Task 1: Update GraphQL Schema

**Goal:** Replace the sync `queryKnowledgeBase` query with a mutation and add `getConversation` query with new types.

**Files to Modify:**
- `src/api/schema.graphql` - Schema changes

**Implementation Steps:**

1. Remove the existing `queryKnowledgeBase` query (line 13 in the Query type):
   ```graphql
   queryKnowledgeBase(query: String!, sessionId: String, conversationId: String): ChatResponse @aws_iam @aws_api_key @aws_cognito_user_pools
   ```

2. Add a new `getConversation` query to the Query type:
   ```graphql
   # Get conversation history by ID (used for polling async chat results)
   getConversation(conversationId: ID!): Conversation @aws_iam @aws_api_key @aws_cognito_user_pools
   ```

3. Add the `queryKnowledgeBase` mutation to the Mutation type (add after existing mutations):
   ```graphql
   # Send a chat query to Knowledge Base (async - returns immediately, poll getConversation for result)
   queryKnowledgeBase(query: String!, conversationId: ID!, requestId: ID!): ChatRequest @aws_iam @aws_api_key @aws_cognito_user_pools
   ```

4. Add new types after the existing `ChatResponse` type. Do NOT remove `ChatResponse` yet (it is still referenced by `searchKnowledgeBase` indirectly and may be used in Python types):

   ```graphql
   # Acknowledgment returned immediately from queryKnowledgeBase mutation
   type ChatRequest @aws_iam @aws_api_key @aws_cognito_user_pools {
     conversationId: ID!
     requestId: ID!
     status: ChatStatus!
   }

   # Status of an individual chat turn
   enum ChatStatus {
     PENDING
     COMPLETED
     ERROR
   }

   # A single conversation turn (message + response pair)
   type ConversationTurn @aws_iam @aws_api_key @aws_cognito_user_pools {
     turnNumber: Int!
     requestId: ID
     status: ChatStatus!
     userMessage: String!
     assistantResponse: String
     sources: [Source!]
     error: String
     createdAt: String!
   }

   # Full conversation with all turns
   type Conversation @aws_iam @aws_api_key @aws_cognito_user_pools {
     conversationId: ID!
     turns: [ConversationTurn!]!
   }
   ```

5. The existing `ChatResponse` type stays for now. It will become unused after the frontend migration but removing it is a separate cleanup.

**Verification Checklist:**
- [x] `queryKnowledgeBase` no longer appears in the `Query` type
- [x] `queryKnowledgeBase` appears in the `Mutation` type with `query`, `conversationId`, `requestId` args
- [x] `getConversation` appears in the `Query` type with `conversationId` arg
- [x] `ChatRequest`, `ChatStatus`, `ConversationTurn`, `Conversation` types are defined
- [x] All new types and fields have `@aws_iam @aws_api_key @aws_cognito_user_pools` auth directives
- [x] `Source` type (already existing) is reused in `ConversationTurn`

**Testing Instructions:**
- No automated test needed. Schema is validated at deploy time by AppSync.
- Verify syntax by visual inspection (matching brackets, correct type references).

**Commit Message Template:**
```
feat(schema): replace sync queryKnowledgeBase query with async mutation

- Remove queryKnowledgeBase from Query type
- Add queryKnowledgeBase mutation with requestId correlation
- Add getConversation query for polling
- Add ChatRequest, ChatStatus, ConversationTurn, Conversation types
```

---

## Task 2: Add Mutation Resolver to AppSync Resolvers

**Goal:** Add a `query_knowledge_base` resolver function in `appsync_resolvers/index.py` that validates input, writes a PENDING record to ConversationHistoryTable, and async-invokes QueryKBFunction.

**Files to Modify:**
- `src/lambda/appsync_resolvers/index.py` - Add resolver function and register in routing

**Prerequisites:**
- Task 1 (schema defines the mutation)

**Implementation Steps:**

1. Add a new environment variable read near the top of the file (near line 161 where `PROCESS_IMAGE_FUNCTION_ARN` is read):
   ```python
   QUERY_KB_FUNCTION_ARN = os.environ.get("QUERY_KB_FUNCTION_ARN")
   ```

2. Also add an env var for the conversation table:
   ```python
   CONVERSATION_TABLE_NAME = os.environ.get("CONVERSATION_TABLE_NAME")
   ```

3. **Register public access check for "chat"** by adding `"queryKnowledgeBase": "chat"` to the `access_requirements` dict in `lambda_handler` (around line 234). This follows the existing pattern where public access is checked in `lambda_handler` *before* the resolver is called, so the resolver does not need access to the full AppSync event for this purpose.

4. **Store identity in a module-level variable** so the resolver can forward it to the async Lambda invocation. In `lambda_handler`, before the `resolver(event["arguments"])` call (line 292), add:
   ```python
   # Store identity for resolvers that need it (e.g., async Lambda invocation)
   _current_identity = event.get("identity")
   ```
   Declare `_current_identity` as a module-level variable (initialized to `None`) near the top of the file. This is safe because Lambda executes one request at a time per container.

5. Add a new resolver function `query_knowledge_base(args)`. Note: per the existing routing pattern at line 292, resolvers receive `event["arguments"]` (the arguments dict), NOT the full AppSync event. The function should:

   a. Extract from `args`: `query` (string), `conversationId` (string), `requestId` (string)
   b. Validate all three are present and non-empty. Raise `ValueError` with descriptive message if missing.
   c. Validate `query` length does not exceed 10000 characters (matching existing validation in query_kb handler).
   d. Skip demo quota here (quota is checked inside QueryKBFunction).
   e. Public access for "chat" is already checked in `lambda_handler` via `access_requirements` (step 3 above). No check needed inside the resolver.
   f. Write a PENDING record to ConversationHistoryTable:
      ```python
      table = dynamodb.Table(CONVERSATION_TABLE_NAME)
      # Determine turn number by querying existing turns
      from boto3.dynamodb.conditions import Key
      response = table.query(
          KeyConditionExpression=Key("conversationId").eq(conversation_id),
          ScanIndexForward=False,
          Limit=1,
          ProjectionExpression="turnNumber",
      )
      existing_items = response.get("Items", [])
      next_turn = int(existing_items[0]["turnNumber"]) + 1 if existing_items else 1

      ttl = int(datetime.now(UTC).timestamp()) + (14 * 86400)  # 14 day TTL

      table.put_item(Item={
          "conversationId": conversation_id,
          "turnNumber": next_turn,
          "requestId": request_id,
          "status": "PENDING",
          "userMessage": query,
          "assistantResponse": "",
          "sources": "[]",
          "createdAt": datetime.now(UTC).isoformat(),
          "ttl": ttl,
      })
      ```
   g. Async-invoke QueryKBFunction following the existing pattern. Use the module-level `_current_identity` variable (set by `lambda_handler` in step 4) to forward the caller's identity:
      ```python
      invoke_event = {
          "arguments": {
              "query": query,
              "conversationId": conversation_id,
          },
          "requestId": request_id,
          "turnNumber": next_turn,
          "identity": _current_identity,
          "asyncInvocation": True,  # Flag so handler knows it's async
      }
      lambda_client.invoke(
          FunctionName=QUERY_KB_FUNCTION_ARN,
          InvocationType="Event",
          Payload=json.dumps(invoke_event).encode(),
      )
      ```
   h. Return the acknowledgment:
      ```python
      return {
          "conversationId": conversation_id,
          "requestId": request_id,
          "status": "PENDING",
      }
      ```

4. Register the new resolver in the `resolvers` dict (around line 251+):
   ```python
   "queryKnowledgeBase": query_knowledge_base,
   ```

5. Error handling: wrap the DynamoDB write and Lambda invoke in try/except. If either fails, raise a `ValueError` with a user-friendly message. Log the actual error.

**Verification Checklist:**
- [x] `QUERY_KB_FUNCTION_ARN` and `CONVERSATION_TABLE_NAME` env vars are read
- [x] `_current_identity` module-level variable is declared and set in `lambda_handler` before resolver call
- [x] `"queryKnowledgeBase": "chat"` is added to `access_requirements` dict in `lambda_handler`
- [x] `query_knowledge_base` function signature accepts `args` (not `event`) matching the resolver call pattern at line 292
- [x] `query_knowledge_base` function validates all 3 required args
- [x] PENDING record is written to DynamoDB before async invoke
- [x] Turn number is calculated by querying existing turns
- [x] `lambda_client.invoke` uses `InvocationType="Event"`
- [x] The `asyncInvocation: True` flag is included in the payload
- [x] The `identity` is forwarded via `_current_identity` module-level variable
- [x] Function is registered in the `resolvers` dict as `"queryKnowledgeBase"`

**Testing Instructions:**

Create a new test file `tests/unit/python/test_async_chat_resolver.py`:

- Mock `boto3.resource("dynamodb")` and `boto3.client("lambda")`
- Test 1: Valid mutation returns `ChatRequest` with PENDING status, correct conversationId and requestId
- Test 2: Missing `query` argument raises ValueError
- Test 3: Missing `conversationId` argument raises ValueError
- Test 4: Missing `requestId` argument raises ValueError
- Test 5: DynamoDB put_item is called with correct PENDING record shape
- Test 6: Lambda invoke is called with correct payload including `asyncInvocation: True`
- Test 7: Public access denied raises ValueError

Run: `uv run pytest tests/unit/python/test_async_chat_resolver.py -v`

**Commit Message Template:**
```
feat(resolver): add async queryKnowledgeBase mutation resolver

- Write PENDING record to ConversationHistoryTable
- Async-invoke QueryKBFunction via lambda_client.invoke(Event)
- Validate input and check public access
- Register in resolver routing dict
```

---

## Task 3: Add getConversation Query Resolver

**Goal:** Add a `get_conversation` resolver that reads all turns for a conversationId from ConversationHistoryTable and returns them in the `Conversation` shape.

**Files to Modify:**
- `src/lambda/appsync_resolvers/index.py` - Add resolver function and register in routing

**Prerequisites:**
- Task 2 (shares CONVERSATION_TABLE_NAME env var)

**Implementation Steps:**

1. Add a `get_conversation(args)` function that (note: per the existing routing pattern at line 292, resolvers receive `event["arguments"]`, not the full event):

   a. Extracts `conversationId` from `args`
   b. Validates it is present and non-empty
   c. Queries ConversationHistoryTable:
      ```python
      table = dynamodb.Table(CONVERSATION_TABLE_NAME)
      response = table.query(
          KeyConditionExpression=Key("conversationId").eq(conversation_id),
          ScanIndexForward=True,  # Chronological order
      )
      ```
   d. Maps DynamoDB items to the `Conversation` GraphQL shape:
      ```python
      turns = []
      for item in response.get("Items", []):
          turn = {
              "turnNumber": int(item["turnNumber"]),
              "requestId": item.get("requestId"),
              "status": item.get("status", "COMPLETED"),  # Legacy turns without status are COMPLETED
              "userMessage": item.get("userMessage", ""),
              "assistantResponse": item.get("assistantResponse"),
              "sources": None,
              "error": item.get("errorMessage"),
              "createdAt": item.get("createdAt", ""),
          }
          # Parse sources from JSON string to list
          sources_json = item.get("sources", "[]")
          if sources_json and sources_json != "[]":
              try:
                  turn["sources"] = json.loads(sources_json)
              except (json.JSONDecodeError, TypeError):
                  turn["sources"] = []
          else:
              turn["sources"] = []
          turns.append(turn)

      return {
          "conversationId": conversation_id,
          "turns": turns,
      }
      ```

2. Register in the `resolvers` dict:
   ```python
   "getConversation": get_conversation,
   ```

3. Add `from boto3.dynamodb.conditions import Key` at the top of the file if not already imported (check existing imports).

**Verification Checklist:**
- [x] `get_conversation` function signature accepts `args` (not `event`) matching the resolver call pattern
- [x] DynamoDB query uses `ScanIndexForward=True` for chronological order
- [x] Legacy turns without `status` attribute default to `"COMPLETED"`
- [x] Sources are parsed from JSON string to list
- [x] Function is registered in resolvers dict as `"getConversation"`
- [x] Returns `Conversation` shape with `conversationId` and `turns` array

**Testing Instructions:**

Add tests to `tests/unit/python/test_async_chat_resolver.py`:

- Test 1: Returns conversation with multiple turns in chronological order
- Test 2: Empty conversation (no turns) returns empty turns array
- Test 3: PENDING turn has null assistantResponse and empty sources
- Test 4: COMPLETED turn has parsed sources array
- Test 5: ERROR turn includes errorMessage
- Test 6: Legacy turns without status attribute default to COMPLETED

Run: `uv run pytest tests/unit/python/test_async_chat_resolver.py -v`

**Commit Message Template:**
```
feat(resolver): add getConversation query resolver

- Query ConversationHistoryTable by conversationId
- Return turns in chronological order with parsed sources
- Handle legacy turns without status attribute
```

---

## Task 4: Modify QueryKB Handler for Async Invocation

**Goal:** Update `query_kb/handler.py` to detect async invocation, skip the AppSync return path, and instead update the PENDING DynamoDB record with the result (COMPLETED or ERROR).

**Files to Modify:**
- `src/lambda/query_kb/handler.py` - Modify `lambda_handler` to support async mode
- `src/lambda/query_kb/conversation.py` - Add `update_conversation_turn` function

**Prerequisites:**
- Task 2 (defines the async invocation payload shape)

**Implementation Steps:**

### 4a: Add `update_conversation_turn` to conversation.py

Add a new function in `src/lambda/query_kb/conversation.py`:

```python
def update_conversation_turn(
    conversation_id: str,
    turn_number: int,
    status: str,
    assistant_response: str = "",
    sources: list[SourceInfo] | None = None,
    error_message: str | None = None,
) -> None:
    """
    Update an existing conversation turn with the async result.

    Args:
        conversation_id: The conversation ID
        turn_number: The turn number to update
        status: "COMPLETED" or "ERROR"
        assistant_response: The assistant's response (for COMPLETED)
        sources: The source documents used (for COMPLETED)
        error_message: Error details (for ERROR)
    """
    conversation_table_name = os.environ.get("CONVERSATION_TABLE_NAME")
    if not conversation_table_name or not conversation_id:
        return

    table = dynamodb.Table(conversation_table_name)

    update_expr = "SET #status = :status, assistantResponse = :response, sources = :sources"
    expr_values: dict[str, Any] = {
        ":status": status,
        ":response": assistant_response,
        ":sources": json.dumps(sources or []),
    }
    expr_names = {"#status": "status"}

    if error_message:
        update_expr += ", errorMessage = :error"
        expr_values[":error"] = error_message

    try:
        table.update_item(
            Key={
                "conversationId": conversation_id,
                "turnNumber": turn_number,
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ExpressionAttributeNames=expr_names,
        )
        logger.info(f"Updated turn {turn_number} for {conversation_id[:8]}... to {status}")
    except ClientError as e:
        logger.error(f"Failed to update conversation turn: {e}")
```

Also add `update_conversation_turn` to the import blocks (both the try/except import patterns at the top of `handler.py`).

### 4b: Modify lambda_handler in handler.py

1. At the top of `lambda_handler`, detect async invocation:
   ```python
   is_async = event.get("asyncInvocation", False)
   request_id = event.get("requestId")
   turn_number = event.get("turnNumber")
   ```

2. When `is_async` is True, the existing handler logic runs as-is (quota check, retrieval, Converse API call), but instead of returning the result dict, it updates the DynamoDB record.

3. Wrap the main try block. After the existing `store_conversation_turn` call (around line 671-677), add the async update path:

   **After the existing `store_conversation_turn` call** (which writes a new turn in the current sync flow), replace the conversation storage logic for async mode:

   When `is_async` is True:
   - Do NOT call `store_conversation_turn` (the PENDING record already exists)
   - Instead call `update_conversation_turn` with COMPLETED status, the answer, and sources
   - Still return the result dict (Lambda return is ignored for async invocations, but it is good practice)

   When `is_async` is False (direct AppSync invocation, for backward compat during transition or tests):
   - Keep existing behavior unchanged

   The change is structured as:
   ```python
   # Store conversation turn for future context
   if conversation_id:
       if is_async and turn_number:
           # Async mode: update existing PENDING record
           update_conversation_turn(
               conversation_id=conversation_id,
               turn_number=turn_number,
               status="COMPLETED",
               assistant_response=answer,
               sources=sources,
           )
       else:
           # Sync mode: create new record (existing behavior)
           next_turn = len(history) + 1
           store_conversation_turn(
               conversation_id=conversation_id,
               turn_number=next_turn,
               user_message=query,
               assistant_response=answer,
               sources=sources,
           )
   ```

4. In the `except ClientError` and `except Exception` blocks (lines 690-709), add async error handling:
   ```python
   if is_async and conversation_id and turn_number:
       update_conversation_turn(
           conversation_id=conversation_id,
           turn_number=turn_number,
           status="ERROR",
           error_message=error_msg_for_user,
       )
   ```
   Where `error_msg_for_user` is the user-facing error string that would have been returned in the `"error"` field.

5. The handler still returns the same ChatResponse dict in all cases. For async invocations, the return value is ignored by Lambda (Event invocation), but it keeps the function signature consistent.

**Verification Checklist:**
- [x] `is_async` flag is read from `event.get("asyncInvocation", False)`
- [x] `request_id` and `turn_number` are extracted from event
- [x] In async mode, `update_conversation_turn` is called instead of `store_conversation_turn`
- [x] In async mode, errors update the DynamoDB record with ERROR status
- [x] In sync mode (no `asyncInvocation` flag), behavior is completely unchanged
- [x] `update_conversation_turn` is imported in handler.py
- [x] `update_conversation_turn` uses `table.update_item` (not put_item) to update existing record

**Testing Instructions:**

Add tests to `tests/unit/python/test_query_kb.py` (extend existing file):

- Test 1: Async invocation calls `update_conversation_turn` with COMPLETED status
- Test 2: Async invocation error calls `update_conversation_turn` with ERROR status
- Test 3: Sync invocation (no asyncInvocation flag) still calls `store_conversation_turn` (existing behavior)
- Test 4: `update_conversation_turn` calls DynamoDB `update_item` with correct key and expression

Create a test for the new function in `tests/unit/python/test_conversation.py` (or add to existing test file if one exists):

- Test 1: `update_conversation_turn` with COMPLETED status writes correct attributes
- Test 2: `update_conversation_turn` with ERROR status includes errorMessage
- Test 3: `update_conversation_turn` with missing table name returns without error

Run: `uv run pytest tests/unit/python/test_query_kb.py tests/unit/python/test_async_chat_resolver.py -v`

**Commit Message Template:**
```
feat(query-kb): support async invocation with DynamoDB result storage

- Add update_conversation_turn for updating PENDING records
- Detect asyncInvocation flag in lambda_handler
- Write COMPLETED/ERROR status to ConversationHistoryTable
- Preserve sync behavior when flag is absent
```

---

## Task 5: Update SAM Template

**Goal:** Wire the new GraphQL resolvers, datasources, and IAM permissions in `template.yaml`.

**Files to Modify:**
- `template.yaml` - Resolver wiring, env vars, IAM permissions

**Prerequisites:**
- Tasks 1-4 (schema and resolver code exist)

**Implementation Steps:**

1. **Change QueryKBResolver from Query to Mutation** (around line 3450-3457):

   Change:
   ```yaml
   QueryKBResolver:
     Type: AWS::AppSync::Resolver
     DependsOn: GraphQLSchema
     Properties:
       ApiId: !GetAtt GraphQLApi.ApiId
       TypeName: Query
       FieldName: queryKnowledgeBase
       DataSourceName: !GetAtt KBQueryDataSource.Name
   ```

   To route the mutation through the AppSync resolver function instead of directly to QueryKBFunction:
   ```yaml
   QueryKBResolver:
     Type: AWS::AppSync::Resolver
     DependsOn: GraphQLSchema
     Properties:
       ApiId: !GetAtt GraphQLApi.ApiId
       TypeName: Mutation
       FieldName: queryKnowledgeBase
       DataSourceName: !GetAtt AppSyncLambdaDataSource.Name
   ```

   Note: The datasource changes from `KBQueryDataSource` (which points to QueryKBFunction) to `AppSyncLambdaDataSource` (which points to AppSyncResolverFunction). The resolver function will async-invoke QueryKBFunction.

2. **Add GetConversationResolver** (after QueryKBResolver):
   ```yaml
   GetConversationResolver:
     Type: AWS::AppSync::Resolver
     DependsOn: GraphQLSchema
     Properties:
       ApiId: !GetAtt GraphQLApi.ApiId
       TypeName: Query
       FieldName: getConversation
       DataSourceName: !GetAtt AppSyncLambdaDataSource.Name
   ```

3. **Add environment variables to AppSyncResolverFunction** (around line 3120-3142):

   Add to the `Variables` section:
   ```yaml
   QUERY_KB_FUNCTION_ARN: !GetAtt QueryKBFunction.Arn
   CONVERSATION_TABLE_NAME: !Ref ConversationHistoryTable
   ```

4. **Add IAM permissions to AppSyncResolverFunction** (around line 3143+):

   Add Lambda invoke permission for QueryKBFunction:
   ```yaml
   - Statement:
       - Effect: Allow
         Action:
           - lambda:InvokeFunction
         Resource: !GetAtt QueryKBFunction.Arn
   ```

   Add DynamoDB read/write permission for ConversationHistoryTable:
   ```yaml
   - DynamoDBCrudPolicy:
       TableName: !Ref ConversationHistoryTable
   ```

5. **Verify QueryKBFunction already has ConversationHistoryTable access** (line 1724, 1733). It does -- `CONVERSATION_TABLE_NAME` env var and `DynamoDBCrudPolicy` are already set. No changes needed.

6. **Do NOT remove the KBQueryDataSource** (line 3331-3334). It is still referenced by AppSync's internal wiring and may be used by `searchKnowledgeBase`. Leave it in place.

**Verification Checklist:**
- [x] `QueryKBResolver` TypeName changed from `Query` to `Mutation`
- [x] `QueryKBResolver` DataSourceName changed to `AppSyncLambdaDataSource`
- [x] `GetConversationResolver` added with TypeName `Query`, FieldName `getConversation`
- [x] `QUERY_KB_FUNCTION_ARN` and `CONVERSATION_TABLE_NAME` added to AppSyncResolverFunction env vars
- [x] Lambda invoke permission for QueryKBFunction added to AppSyncResolverFunction policies
- [x] DynamoDB CRUD permission for ConversationHistoryTable added to AppSyncResolverFunction policies
- [x] KBQueryDataSource is NOT removed
- [x] QueryKBFunction env vars and policies are unchanged

**Testing Instructions:**
- No automated test. SAM template validation happens at build/deploy time.
- Verify YAML syntax: `python -c "import yaml; yaml.safe_load(open('template.yaml'))"`
- Check for indentation consistency with surrounding resources.

**Commit Message Template:**
```
chore(template): wire async chat resolvers and permissions

- Route queryKnowledgeBase mutation through AppSyncResolverFunction
- Add getConversation resolver
- Add QUERY_KB_FUNCTION_ARN and CONVERSATION_TABLE_NAME env vars
- Add Lambda invoke and DynamoDB permissions
```

---

## Task 6: Run Full Backend Test Suite

**Goal:** Verify all existing and new tests pass.

**Files to Modify:** None (verification only)

**Prerequisites:**
- Tasks 1-5 complete

**Implementation Steps:**

1. Run the full Python test suite:
   ```bash
   uv run pytest tests/unit/python/ -v
   ```

2. Run lint:
   ```bash
   npm run lint
   ```

3. Fix any failures. Common issues:
   - Existing tests that mock the sync `queryKnowledgeBase` query path may need updates if they test AppSync resolver routing
   - Import paths for `update_conversation_turn` may need adjustment
   - Ruff formatting: run `npm run lint:fix`

**Verification Checklist:**
- [x] All tests in `tests/unit/python/` pass
- [x] `npm run lint` passes with no errors
- [x] No regressions in existing test_query_kb.py tests

**Commit Message Template:**
```
test(backend): verify all backend tests pass with async chat changes

- Fix any test regressions from sync-to-async migration
```

---

## Phase Verification

After completing all tasks in Phase 1:

1. **Schema:** `src/api/schema.graphql` has mutation `queryKnowledgeBase`, query `getConversation`, and new types
2. **Resolver:** `appsync_resolvers/index.py` has `query_knowledge_base` and `get_conversation` functions
3. **Handler:** `query_kb/handler.py` detects `asyncInvocation` flag and updates DynamoDB accordingly
4. **Conversation:** `query_kb/conversation.py` has `update_conversation_turn` function
5. **Template:** `template.yaml` routes mutation through AppSyncResolverFunction with correct permissions
6. **Tests:** All Python tests pass, new tests cover async flow

**Known limitations:**
- Frontend still uses the old sync query (will break until Phase 2 is complete)
- The `ChatResponse` type remains in the schema (unused but harmless)
- The `KBQueryDataSource` remains (still used by searchKnowledgeBase resolver)
