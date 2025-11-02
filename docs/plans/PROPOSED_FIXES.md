  Critical Issues

  1. Phase 1 Has a Fundamental Gap

  Problem: Phase 1 (Task 1.2) assumes configuration schema is defined in the AppSync resolver Lambda, but based on the CLAUDE.md description,
  lib/ragstack_common/config.py already has a ConfigurationManager that reads from DynamoDB.

  Missing Clarity:
  - Where exactly IS the schema defined initially? In DynamoDB data? In Lambda code? In a bootstrap script?
  - How does the DynamoDB Configuration table get populated with Schema/Default/Custom?
  - Task 1.2 says "Update the configuration schema" but doesn't specify if this is code or data

  Recommendation: Add a Task 1.0 that explicitly states:
  - Examine current ConfigurationManager implementation
  - Identify where schema is defined (code vs data)
  - Document the update mechanism (code change vs DynamoDB update)

  2. Missing IAM/Environment Variable Updates in Phase 1

  Problem: Phase 1 adds fields to configuration but doesn't update the Lambda functions that will READ these fields until Phase 3.

  Gap: ProcessDocument Lambda needs to read ocr_backend and bedrock_ocr_model_id but:
  - No IAM permissions added in Phase 1
  - No environment variables set in Phase 1
  - Phase 3 only updates QueryKB, not ProcessDocument

  Recommendation: Either:
  - Add Task 1.5: Update ProcessDocument Lambda to read OCR config
  - OR explicitly state in Phase 1 that OCR config won't be used until later (breaking the feature into backend/frontend/integration)

  3. Phase 2 Assumption May Be Wrong

  Problem: Task 2.1 assumes "minimal or no code changes expected" because Settings is schema-driven.

  Risk: The dependsOn conditional logic may not exist yet. You're assuming:
  // lines 228-236 mentioned in plan
  if (field.dependsOn && formValues[field.dependsOn.field] !== field.dependsOn.value) {
    return null; // hide field
  }

  But: If this pattern doesn't exist in the current codebase, Phase 2 will require MORE work than estimated.

  Recommendation:
  - Add to Task 2.1: "Verify dependsOn logic exists in renderField function"
  - If missing, add implementation task (not just testing)
  - Adjust token estimate accordingly

  4. Phase 3 Session Management Confusion

  Problem: Task 3.2 implementation shows sessionId passthrough, but there's confusion about WHERE the QueryKB Lambda currently lives.

  Questions the plan doesn't answer:
  - Is QueryKB a separate Lambda or part of AppSync resolvers?
  - If separate: how is it invoked? Direct Lambda invoke or via AppSync?
  - If via AppSync: Task 3.3 seems redundant (why update routing if it's a separate Lambda?)

  Recommendation:
  - Add architecture diagram showing current QueryKB invocation flow
  - Clarify if this is direct invoke, AppSync Lambda resolver, or AppSync HTTP resolver
  - Adjust Task 3.3 based on actual architecture

  5. Missing Re-embedding Workflow Detail

  Problem: Phase 2 mentions "preserve existing re-embedding workflow" but provides no detail on HOW it works.

  Risks:
  - What if the modal logic checks ALL config changes?
  - What if it compares old/new config objects and new OCR fields trigger false positives?
  - The plan assumes it only checks embedding fields but provides no verification

  Recommendation: Add to Phase 2 Task 2.1:
  - Read and document exact re-embedding trigger logic
  - Verify field names being checked
  - Test that new fields don't interfere

  6. GraphQL Schema Update Timing

  Problem: Phase 1 Task 1.1 says "document new fields in code comments" but Phase 3 Task 3.1 says "update query signature."

  Confusion:
  - Are these the same schema file?
  - Does Phase 1 actually change the GraphQL schema or just add comments?
  - Why are there two separate schema update tasks?

  Recommendation: Clarify:
  - Phase 1 is for Configuration type only (getConfiguration query)
  - Phase 3 is for QueryKB type only (queryKnowledgeBase query)
  - Make this explicit to avoid confusion

  Minor Issues

  7. Test File Locations Inconsistent

  Phase 1 shows:
  - src/lambda/appsync_resolvers/test_configuration.py
  - lib/ragstack_common/test_config.py

  But Python convention is usually:
  - tests/unit/ or tests/integration/ directories
  - OR test_*.py files alongside source

  Recommendation: Verify actual test directory structure and update paths in plan.

  8. Missing Rollback Strategy

  Problem: Plan is "local development only" but doesn't address:
  - What if Phase 2 frontend expects Phase 1 backend changes that aren't deployed?
  - How to keep frontend/backend in sync during development?
  - What happens when testing locally with real AWS resources (config table)?

  Recommendation: Add section on:
  - Mock/stub strategies for testing frontend without deployed backend
  - Local DynamoDB setup (SAM local DynamoDB) if needed
  - Environment switching strategy

  9. Frontend Test Mocking Pattern Unclear

  Problem: Phase 2 and 4 show extensive GraphQL mocking but don't explain:
  - Is there a shared mock setup?
  - How are Amplify v6 mocks structured?
  - Do existing tests provide patterns to follow?

  Recommendation: Add to Phase 0:
  - Example of existing frontend test with GraphQL mock
  - Link to Amplify v6 testing documentation
  - Pattern for mock client factory (reusable across tests)

  10. Token Estimates May Be Low

  Concern: Phase 3 is estimated at 30k tokens but includes:
  - Comprehensive Lambda implementation (~400 lines of code)
  - Full test suite (~600 lines of test code)
  - IAM updates
  - Local verification
  - Troubleshooting

  Historical data: Writing 1000 lines of quality code + tests typically consumes 40-50k tokens.

  Recommendation: Consider increasing Phase 3 estimate to 35-40k tokens for buffer.
