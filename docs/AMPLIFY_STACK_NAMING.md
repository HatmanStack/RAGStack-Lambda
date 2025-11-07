# Amplify Gen 2 Stack Naming Strategy

## Context

During Phase 1 implementation of the Amplify-to-CodeBuild migration, we discovered that **Amplify Gen 2 stack names are read-only** and cannot be customized.

## Original Plan vs. Reality

### Original Plan (Phase-1.md Task 1.4)
```typescript
// Set stack names explicitly (required for Phase 2 output retrieval)
cdnStack.stackName = `amplify-${projectName}-cdn`;
authStack.stackName = `amplify-${projectName}-auth`;
dataStack.stackName = `amplify-${projectName}-data`;
```

### Reality
```typescript
// ERROR: TS2540: Cannot assign to 'stackName' because it is a read-only property.
```

## Why Stack Names Are Read-Only

Amplify Gen 2 uses CDK under the hood and generates stack names automatically using a pattern:

```
amplify-{backend-id}-{resource-type}-{hash}
```

Example actual stack names:
- `amplify-ragstack-abc123-auth-xyz789`
- `amplify-ragstack-abc123-data-def456`
- `amplify-ragstack-abc123-sandbox-123abc`

The `backend-id` is derived from the directory structure and cannot be overridden via the `defineBackend()` API.

## Chosen Approach: Pattern Matching

Since explicit naming is not possible, **Phase 2 will discover Amplify stacks using name pattern matching**.

### Implementation in backend.ts

```typescript
// Add tags to CDN stack (custom stack we control)
Tags.of(cdnStack).add('Project', projectName);
Tags.of(cdnStack).add('ManagedBy', 'CDK-Amplify');
Tags.of(cdnStack).add('AmplifyStackType', 'cdn');

// Auth and data stacks use Amplify's auto-generated names
// Pattern: amplify-{backend-id}-{resource-type}-{hash}
// Phase 2 will discover them by name pattern: amplify-*-{auth|data}-*
```

### Discovery in Phase 2 (publish.py)

```python
def get_amplify_stack_outputs(project_name, region):
    """
    Discover Amplify stacks by name pattern.

    Amplify Gen 2 creates stacks with auto-generated names like:
    - amplify-*-auth-*
    - amplify-*-data-*
    - amplify-*-sandbox-* (custom stacks)
    """
    cf_client = boto3.client('cloudformation', region_name=region)

    # Search for stacks matching Amplify naming pattern
    paginator = cf_client.get_paginator('list_stacks')
    amplify_stacks = []

    for page in paginator.paginate(StackStatusFilter=['CREATE_COMPLETE', 'UPDATE_COMPLETE']):
        for stack in page['StackSummaries']:
            stack_name = stack['StackName']

            # Match Amplify Gen 2 stack names
            if stack_name.startswith('amplify-') and any(
                resource_type in stack_name
                for resource_type in ['-auth-', '-data-', '-sandbox-']
            ):
                # Verify this is our project by checking tags or outputs
                stack_details = cf_client.describe_stacks(StackName=stack_name)
                tags = {tag['Key']: tag['Value']
                        for tag in stack_details['Stacks'][0].get('Tags', [])}

                # CDN stack has Project tag, auth/data might not
                if tags.get('Project') == project_name or stack_name.startswith(f'amplify-{project_name}'):
                    amplify_stacks.append(stack_name)

    return amplify_stacks
```

## Alternatives Considered

### 1. Tag-Based Discovery (Original Fix)
**Rejected** because:
- Auth and data stacks are managed internally by Amplify
- Cannot access `backend.auth.resources.userPool.stack` (not exposed in public API)
- TypeScript compilation errors when trying to tag internal stacks

### 2. CDK Stack Synthesizer Override
**Rejected** because:
- Amplify Gen 2 wraps CDK and doesn't expose synthesizer configuration
- Would require forking or monkey-patching Amplify libraries
- Too fragile and breaks with updates

### 3. Pattern Matching (Chosen)
**Selected** because:
- Works with Amplify's default behavior
- No TypeScript errors
- Reliable discovery mechanism
- Future-proof (Amplify unlikely to change naming convention)

## Trade-offs

### Advantages
✅ No TypeScript compilation errors
✅ Works with Amplify Gen 2 as designed
✅ No need to access internal APIs
✅ Simple implementation in Phase 2
✅ Future-proof against Amplify updates

### Disadvantages
❌ Stack names not immediately obvious from project name
❌ Requires pattern matching logic in publish.py
❌ Multiple projects in same account need careful filtering
❌ Stack discovery slightly slower (must list all stacks)

## Verification Strategy

To ensure correct stack discovery, Phase 2 will:

1. **List all stacks** with `CREATE_COMPLETE` or `UPDATE_COMPLETE` status
2. **Filter by name pattern**: `amplify-*-{auth|data|sandbox}-*`
3. **Verify ownership** by checking:
   - Tags: `Project={projectName}` (if available)
   - Stack name prefix: `amplify-{projectName}*` (fallback)
4. **Validate outputs** exist before proceeding

## Migration Impact

This decision affects:

- ✅ **Phase-0.md**: Updated ADR-002 to document read-only nature
- ✅ **Phase-1.md**: Updated Task 1.4 to remove stack naming code
- ✅ **Phase-2.md**: Updated Task 2.3 to use pattern matching
- ✅ **amplify/backend.ts**: Removed broken stack naming code
- ✅ **FIXES_APPLIED.md**: Updated to reflect pattern matching approach

## Conclusion

**Pattern matching is the correct approach** for Amplify Gen 2 stack discovery because:

1. It respects Amplify's architecture (no hacks)
2. It avoids TypeScript errors from accessing internal APIs
3. It's maintainable and future-proof
4. It works reliably with Amplify's auto-generated names

The original plan to set explicit stack names was based on the assumption that CDK stacks allow name overrides, but Amplify Gen 2 intentionally restricts this to maintain internal consistency.
