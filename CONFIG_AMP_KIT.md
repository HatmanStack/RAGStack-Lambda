# Amplify AI Kit Configuration Guide

## Overview

This guide explains how to configure the Amplify AI Kit backend to enable full chat functionality in the `<amplify-chat>` web component. Currently, the web component infrastructure is working, but the AIConversation component is replaced with a placeholder pending backend configuration.

**Current Status:**
- ✅ Web component loads and registers
- ✅ React rendering works
- ✅ Props pass through correctly
- ⚠️ AIConversation commented out (requires backend)
- ⚠️ Placeholder UI displayed instead

**Next Steps:** Follow this guide to configure the backend and restore full chat functionality.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Architecture Overview](#architecture-overview)
3. [GraphQL Schema Configuration](#graphql-schema-configuration)
4. [Lambda Resolver Setup](#lambda-resolver-setup)
5. [AIConversation Component Restoration](#aiconversation-component-restoration)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Services

- ✅ AWS Account with Bedrock access
- ✅ Bedrock Knowledge Base (already configured)
- ✅ AppSync GraphQL API (deployed via Amplify)
- ✅ Cognito User Pool (deployed via SAM)
- ✅ Lambda functions for query execution

### Required Permissions

Ensure your AWS credentials have:
- `bedrock:InvokeModel` - For AI model invocation
- `bedrock:Retrieve` - For Knowledge Base queries
- `appsync:*` - For GraphQL API management
- `lambda:InvokeFunction` - For resolver execution

### Check Existing Resources

```bash
# Verify Knowledge Base exists
aws bedrock-agent list-knowledge-bases

# Verify AppSync API exists
aws appsync list-graphql-apis

# Verify Cognito User Pool
aws cognito-idp list-user-pools --max-results 10
```

---

## Architecture Overview

### Current Stack

```
┌─────────────────────────────────────────────────────────────┐
│                   Current Architecture                       │
└─────────────────────────────────────────────────────────────┘

User Browser
  ↓
<amplify-chat> Web Component
  ↓
Placeholder UI (TEMPORARY)
  ↓
❌ AIConversation (commented out)
```

### Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Target Architecture                       │
└─────────────────────────────────────────────────────────────┘

User Browser
  ↓
<amplify-chat> Web Component
  ↓
AIConversation Component (@aws-amplify/ui-react-ai)
  ↓
AppSync GraphQL API
  ↓
Lambda Resolver (ConversationHandler)
  ↓
Amazon Bedrock (Claude/Titan models)
  ↓
Bedrock Knowledge Base (RAG context)
```

### Data Flow

1. User types message in chat UI
2. AIConversation sends GraphQL mutation
3. AppSync routes to Lambda resolver
4. Lambda queries Knowledge Base for context
5. Lambda sends prompt + context to Bedrock
6. Bedrock returns streaming response
7. Lambda formats and returns to AppSync
8. AIConversation displays response with sources

---

## GraphQL Schema Configuration

### Step 1: Define Conversation Types

Edit `amplify/data/resource.ts`:

```typescript
import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

const schema = a.schema({
  // Conversation type
  Conversation: a.model({
    id: a.id().required(),
    userId: a.string().required(),
    title: a.string(),
    createdAt: a.datetime(),
    updatedAt: a.datetime(),
    messages: a.hasMany('Message', 'conversationId'),
  }).authorization(allow => [allow.owner()]),

  // Message type
  Message: a.model({
    id: a.id().required(),
    conversationId: a.id().required(),
    conversation: a.belongsTo('Conversation', 'conversationId'),
    role: a.enum(['user', 'assistant']),
    content: a.string().required(),
    sources: a.json(),  // Array of source citations
    timestamp: a.datetime(),
  }).authorization(allow => [allow.owner()]),

  // Custom query for AI chat
  chat: a.query()
    .arguments({
      conversationId: a.string().required(),
      message: a.string().required(),
    })
    .returns(a.ref('Message'))
    .authorization(allow => [allow.authenticated()])
    .handler(a.handler.function('ConversationHandler')),

  // Streaming response (optional)
  streamChat: a.subscription()
    .for(a.ref('chat'))
    .authorization(allow => [allow.authenticated()]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
    userPoolAuthorizationMode: {
      userPoolId: process.env.USERPOOLID!,
    },
  },
});
```

### Step 2: Deploy Schema

```bash
# Deploy updated schema
npx ampx sandbox  # For development
# OR
npx ampx pipeline-deploy --branch main  # For production
```

### Step 3: Verify Schema Deployed

```bash
# Get API endpoint
aws appsync list-graphql-apis \
  --query "graphqlApis[?contains(name, 'amplify')].{Name:name,Endpoint:uris.GRAPHQL}" \
  --output table

# Download schema
aws appsync get-introspection-schema \
  --api-id <YOUR_API_ID> \
  --format SDL \
  schema.graphql
```

---

## Lambda Resolver Setup

### Step 1: Create Conversation Handler Lambda

Create `src/lambda/conversation_handler/handler.py`:

```python
"""
Conversation Handler Lambda
Resolves chat queries by retrieving context from Knowledge Base and querying Bedrock
"""

import json
import os
import boto3
from datetime import datetime
from typing import Dict, List, Any

# Initialize AWS clients
bedrock_runtime = boto3.client('bedrock-runtime', region_name=os.environ['AWS_REGION'])
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime', region_name=os.environ['AWS_REGION'])

KNOWLEDGE_BASE_ID = os.environ['KNOWLEDGE_BASE_ID']
MODEL_ID = os.environ.get('MODEL_ID', 'anthropic.claude-3-sonnet-20240229-v1:0')

def retrieve_context(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve relevant context from Knowledge Base

    Args:
        query: User's question
        num_results: Number of results to retrieve

    Returns:
        List of source documents with content and metadata
    """
    response = bedrock_agent_runtime.retrieve(
        knowledgeBaseId=KNOWLEDGE_BASE_ID,
        retrievalQuery={'text': query},
        retrievalConfiguration={
            'vectorSearchConfiguration': {
                'numberOfResults': num_results
            }
        }
    )

    sources = []
    for result in response.get('retrievalResults', []):
        sources.append({
            'content': result['content']['text'],
            'source': result.get('location', {}).get('s3Location', {}).get('uri', 'Unknown'),
            'score': result.get('score', 0.0),
        })

    return sources

def format_prompt(user_message: str, context: List[Dict[str, Any]]) -> str:
    """
    Format prompt with retrieved context

    Args:
        user_message: User's question
        context: Retrieved source documents

    Returns:
        Formatted prompt for Bedrock
    """
    context_text = "\n\n".join([
        f"Source {i+1} ({source['source']}):\n{source['content']}"
        for i, source in enumerate(context)
    ])

    return f"""You are a helpful AI assistant. Answer the user's question based on the provided context.

Context from knowledge base:
{context_text}

User's question: {user_message}

Provide a detailed answer based on the context. If the context doesn't contain enough information to fully answer the question, acknowledge this limitation."""

def invoke_bedrock(prompt: str) -> str:
    """
    Invoke Bedrock model with prompt

    Args:
        prompt: Formatted prompt

    Returns:
        AI-generated response
    """
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "top_p": 0.9,
    })

    response = bedrock_runtime.invoke_model(
        modelId=MODEL_ID,
        body=body
    )

    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text']

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AppSync Lambda resolver handler

    Args:
        event: AppSync event with arguments
        context: Lambda context

    Returns:
        Message object for GraphQL response
    """
    print(f"Event: {json.dumps(event)}")

    # Extract arguments
    arguments = event.get('arguments', {})
    conversation_id = arguments.get('conversationId')
    user_message = arguments.get('message')

    # Retrieve context from Knowledge Base
    print(f"Retrieving context for: {user_message}")
    sources = retrieve_context(user_message)

    # Format prompt with context
    prompt = format_prompt(user_message, sources)

    # Get AI response from Bedrock
    print(f"Invoking Bedrock model: {MODEL_ID}")
    ai_response = invoke_bedrock(prompt)

    # Format response
    message = {
        'id': f"msg-{datetime.utcnow().timestamp()}",
        'conversationId': conversation_id,
        'role': 'assistant',
        'content': ai_response,
        'sources': [
            {
                'uri': source['source'],
                'score': source['score'],
            }
            for source in sources[:3]  # Top 3 sources
        ],
        'timestamp': datetime.utcnow().isoformat(),
    }

    print(f"Response generated: {len(ai_response)} chars, {len(sources)} sources")
    return message
```

### Step 2: Update SAM Template

Add Lambda to `template.yaml`:

```yaml
  ConversationHandlerFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub '${ProjectName}-conversation-handler-${DeploymentSuffix}'
      CodeUri: src/lambda/conversation_handler/
      Handler: handler.handler
      Runtime: python3.13
      Timeout: 30
      MemorySize: 512
      Environment:
        Variables:
          KNOWLEDGE_BASE_ID: !GetAtt KnowledgeBase.KnowledgeBaseId
          AWS_REGION: !Ref AWS::Region
          MODEL_ID: anthropic.claude-3-sonnet-20240229-v1:0
      Policies:
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
                - bedrock:InvokeModelWithResponseStream
              Resource: !Sub 'arn:aws:bedrock:${AWS::Region}::foundation-model/*'
            - Effect: Allow
              Action:
                - bedrock:Retrieve
              Resource: !GetAtt KnowledgeBase.KnowledgeBaseArn
```

### Step 3: Connect Lambda to AppSync

Update `amplify/data/resource.ts`:

```typescript
import { defineFunction } from '@aws-amplify/backend';

// Define Lambda function reference
export const conversationHandler = defineFunction({
  name: 'ConversationHandler',
  entry: '../../src/lambda/conversation_handler/handler.ts',  // Or .py if using Python
  runtime: 20,  // Node.js 20
});

// In schema:
const schema = a.schema({
  // ...
  chat: a.query()
    .arguments({
      conversationId: a.string().required(),
      message: a.string().required(),
    })
    .returns(a.ref('Message'))
    .authorization(allow => [allow.authenticated()])
    .handler(a.handler.function(conversationHandler)),  // Connect Lambda
});
```

### Step 4: Deploy Lambda

```bash
# Deploy SAM stack with new Lambda
sam build
sam deploy

# Deploy Amplify backend with updated schema
npx ampx sandbox
```

---

## AIConversation Component Restoration

### Step 1: Uncomment AIConversation Import

Edit `src/amplify-chat/src/components/ChatWithSources.tsx`:

```typescript
import React, { useCallback, useMemo, useEffect, useRef } from 'react';
import { AIConversation } from '@aws-amplify/ui-react-ai';  // ← Uncomment this
import { SourcesDisplay } from './SourcesDisplay';
// ...
```

### Step 2: Replace Placeholder with AIConversation

```typescript
export const ChatWithSources: React.FC<ChatWithSourcesProps> = ({
  conversationId = 'default',
  // ... other props
}) => {
  // ...

  return (
    <div ref={containerRef} className={styles.chatContainer} style={containerStyle}>
      {/* Header */}
      <div className={styles.chatHeader}>
        <h1 className={styles.headerTitle}>{headerText}</h1>
        {headerSubtitle && <p className={styles.headerSubtitle}>{headerSubtitle}</p>}
      </div>

      {/* Chat Content */}
      <div className={styles.chatContent}>
        <AIConversation
          id={conversationId}
          allowAttachments={false}
          responseComponents={{
            Message: ({ content, sources }) => (
              <div className={styles.responseContainer}>
                <p className={styles.responseText}>{content}</p>
                {showSources && sources && sources.length > 0 && (
                  <SourcesDisplay sources={sources} />
                )}
              </div>
            ),
          }}
        />
      </div>

      {/* Footer */}
      <div className={styles.chatFooter}>
        <p className={styles.footerText}>
          Responses are sourced from your knowledge base
        </p>
      </div>
    </div>
  );
};
```

### Step 3: Configure AIConversation Props

Refer to [@aws-amplify/ui-react-ai documentation](https://ui.docs.amplify.aws/react/connected-components/ai/conversation) for full API.

**Minimal Props:**
```typescript
<AIConversation
  id={conversationId}              // Required: Unique conversation ID
  allowAttachments={false}         // Optional: Disable file uploads
/>
```

**Advanced Props:**
```typescript
<AIConversation
  id={conversationId}
  allowAttachments={false}
  variant="bubble"                 // Chat bubble style
  aiContext={{                     // Additional context
    userId: userId || undefined,
    knowledgeBaseId: KNOWLEDGE_BASE_ID,
  }}
  responseComponents={{             // Custom message rendering
    Message: ({ content, sources }) => (
      <div>
        <p>{content}</p>
        {sources && <SourcesDisplay sources={sources} />}
      </div>
    ),
  }}
  suggestedPrompts={[              // Initial suggestions
    { prompt: 'What can you help me with?' },
    { prompt: 'Tell me about my documents' },
  ]}
/>
```

### Step 4: Rebuild and Deploy

```bash
# Rebuild web component
cd src/amplify-chat
npm run build:wc

# Deploy via publish.py
cd ../..
python publish.py \
  --project-name your-project \
  --admin-email your@email.com \
  --region us-west-2 \
  --chat-only
```

---

## Testing

### Step 1: Test GraphQL API Directly

Use AWS AppSync Console or curl:

```bash
# GraphQL mutation to test chat
curl -X POST https://YOUR_API.appsync-api.us-west-2.amazonaws.com/graphql \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "query": "mutation Chat($conversationId: String!, $message: String!) { chat(conversationId: $conversationId, message: $message) { id role content sources { uri score } timestamp } }",
    "variables": {
      "conversationId": "test-123",
      "message": "What information do you have?"
    }
  }'
```

**Expected Response:**
```json
{
  "data": {
    "chat": {
      "id": "msg-1699123456.789",
      "role": "assistant",
      "content": "Based on the documents in the knowledge base...",
      "sources": [
        {
          "uri": "s3://bucket/doc1.pdf",
          "score": 0.95
        }
      ],
      "timestamp": "2024-11-08T00:00:00.000Z"
    }
  }
}
```

### Step 2: Test in Browser

Open test page:

```html
<!DOCTYPE html>
<html>
<head>
  <title>AI Chat Test</title>
</head>
<body>
  <h1>AI Chat Test</h1>

  <amplify-chat
    conversation-id="test-chat"
    header-text="Document Q&A"
    show-sources="true"
  ></amplify-chat>

  <script src="https://YOUR_DISTRIBUTION.cloudfront.net/amplify-chat.js"></script>
</body>
</html>
```

**Expected Behavior:**
1. Chat UI renders with input box
2. Type message and press send
3. Loading indicator appears
4. AI response displays with sources
5. Sources are clickable/expandable

### Step 3: Check Console Logs

```javascript
// Should see:
[AmplifyChat] Bundle loading...
[AmplifyChat] Amplify configured successfully
[AmplifyChat] Custom element registered successfully
[AmplifyChat] connectedCallback - element added to DOM
[AmplifyChat] render() called
[AmplifyChat] React root created
[AmplifyChat] Rendering with props: {...}

// AIConversation logs:
[AIConversation] Message sent: "What information do you have?"
[AIConversation] Response received: {...}
```

### Step 4: Verify Sources Display

The `SourcesDisplay` component should show:
- Source document name
- Confidence score
- Click to expand full citation
- Proper styling from CSS modules

---

## Troubleshooting

### Issue: "Cannot read properties of undefined (reading 'length')"

**Cause:** AIConversation expects specific GraphQL schema structure.

**Solution:**
1. Verify schema has `Message` type with `sources` field
2. Ensure Lambda returns array for `sources`, not object
3. Check AppSync resolver correctly maps response

```typescript
// Lambda MUST return:
{
  sources: [
    { uri: 'string', score: number },  // ← Array of objects
  ]
}

// NOT:
{
  sources: { uri: 'string', score: number }  // ← Single object
}
```

### Issue: "No data returned from chat query"

**Cause:** Lambda resolver not connected or failing.

**Solution:**
1. Check CloudWatch logs for Lambda errors:
   ```bash
   aws logs tail /aws/lambda/YourProject-conversation-handler --follow
   ```

2. Verify IAM permissions for Bedrock access

3. Test Lambda directly:
   ```bash
   aws lambda invoke \
     --function-name YourProject-conversation-handler \
     --payload '{"arguments":{"conversationId":"test","message":"Hello"}}' \
     response.json
   ```

### Issue: "Authentication error"

**Cause:** User not signed in or token expired.

**Solution:**
1. Wrap component in Amplify Authenticator:
   ```typescript
   import { Authenticator } from '@aws-amplify/ui-react';

   <Authenticator>
     {({ signOut, user }) => (
       <amplify-chat conversation-id={user.username} />
     )}
   </Authenticator>
   ```

2. Or configure public access in schema:
   ```typescript
   .authorization(allow => [allow.publicApiKey()])
   ```

### Issue: "Sources not displaying"

**Cause:** CSS modules not loading or wrong prop structure.

**Solution:**
1. Verify `cssCodeSplit: false` in vite.wc.config.ts
2. Check `sources` array structure matches SourcesDisplay props:
   ```typescript
   interface Source {
     uri: string;
     score: number;
     title?: string;
   }
   ```

3. Add console.log in SourcesDisplay to debug:
   ```typescript
   export const SourcesDisplay = ({ sources }: SourcesDisplayProps) => {
     console.log('SourcesDisplay received:', sources);
     // ...
   }
   ```

### Issue: "Streaming not working"

**Cause:** Bedrock streaming requires different API call.

**Solution:**
1. Use `invoke_model_with_response_stream` instead of `invoke_model`:
   ```python
   response = bedrock_runtime.invoke_model_with_response_stream(
       modelId=MODEL_ID,
       body=body
   )

   for event in response['body']:
       chunk = json.loads(event['chunk']['bytes'])
       # Send chunk via AppSync subscription
   ```

2. Implement AppSync subscription for streaming:
   ```typescript
   streamChat: a.subscription()
     .for(a.ref('chat'))
     .handler(a.handler.function(conversationHandler))
   ```

---

## Performance Optimization

### Caching Responses

```python
import hashlib
from functools import lru_cache

@lru_cache(maxsize=100)
def retrieve_context_cached(query: str, num_results: int = 5):
    """Cache Knowledge Base retrievals for identical queries"""
    return retrieve_context(query, num_results)
```

### Parallel Processing

```python
import asyncio

async def handle_chat_async(user_message: str) -> Dict[str, Any]:
    # Retrieve context and invoke Bedrock in parallel
    context_task = asyncio.create_task(retrieve_context_async(user_message))
    # Could also fetch conversation history in parallel

    context = await context_task
    prompt = format_prompt(user_message, context)

    response = await invoke_bedrock_async(prompt)
    return response
```

### Response Streaming

For better UX, stream responses token-by-token:

```python
def invoke_bedrock_streaming(prompt: str):
    """Stream tokens as they're generated"""
    response = bedrock_runtime.invoke_model_with_response_stream(
        modelId=MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        })
    )

    for event in response['body']:
        chunk = json.loads(event['chunk']['bytes'])
        if 'delta' in chunk:
            yield chunk['delta']['text']
```

---

## Security Considerations

### Input Validation

```python
def validate_input(message: str) -> bool:
    """Validate user input before processing"""
    if len(message) > 10000:
        raise ValueError("Message too long")

    if not message.strip():
        raise ValueError("Message cannot be empty")

    # Add your custom validation
    return True
```

### Rate Limiting

```python
from functools import wraps
import time

# Simple in-memory rate limiter (use DynamoDB for production)
rate_limit_cache = {}

def rate_limit(max_requests=10, window_seconds=60):
    def decorator(func):
        @wraps(func)
        def wrapper(event, context):
            user_id = event['identity']['username']
            now = time.time()

            # Clean old entries
            rate_limit_cache[user_id] = [
                t for t in rate_limit_cache.get(user_id, [])
                if now - t < window_seconds
            ]

            if len(rate_limit_cache[user_id]) >= max_requests:
                raise Exception("Rate limit exceeded")

            rate_limit_cache[user_id].append(now)
            return func(event, context)
        return wrapper
    return decorator

@rate_limit(max_requests=10, window_seconds=60)
def handler(event, context):
    # Your handler code
    pass
```

### Content Filtering

```python
def filter_response(text: str) -> str:
    """Filter inappropriate content from AI responses"""
    # Use AWS Comprehend for content moderation
    comprehend = boto3.client('comprehend')

    response = comprehend.detect_pii_entities(
        Text=text,
        LanguageCode='en'
    )

    # Redact PII if found
    for entity in response['Entities']:
        if entity['Type'] in ['SSN', 'CREDIT_DEBIT_NUMBER', 'EMAIL']:
            text = text.replace(
                text[entity['BeginOffset']:entity['EndOffset']],
                '[REDACTED]'
            )

    return text
```

---

## Monitoring and Logging

### CloudWatch Metrics

```python
import boto3
cloudwatch = boto3.client('cloudwatch')

def log_metrics(conversation_id: str, latency: float, num_sources: int):
    """Send custom metrics to CloudWatch"""
    cloudwatch.put_metric_data(
        Namespace='AmplifyChat',
        MetricData=[
            {
                'MetricName': 'ResponseLatency',
                'Value': latency,
                'Unit': 'Milliseconds',
                'Dimensions': [
                    {'Name': 'ConversationId', 'Value': conversation_id}
                ]
            },
            {
                'MetricName': 'SourcesRetrieved',
                'Value': num_sources,
                'Unit': 'Count',
            }
        ]
    )
```

### Structured Logging

```python
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_event(event_type: str, data: Dict[str, Any]):
    """Log structured events for analysis"""
    logger.info(json.dumps({
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'data': data
    }))

# Usage:
log_event('chat_request', {
    'conversation_id': conversation_id,
    'message_length': len(user_message),
    'user_id': user_id
})
```

---

## Next Steps

1. **Complete Backend Setup** (This Guide)
   - [ ] Configure GraphQL schema
   - [ ] Deploy conversation handler Lambda
   - [ ] Connect Lambda to AppSync

2. **Restore AIConversation Component**
   - [ ] Uncomment import
   - [ ] Replace placeholder
   - [ ] Test end-to-end

3. **Advanced Features** (Future)
   - [ ] Implement streaming responses
   - [ ] Add conversation history
   - [ ] Custom theming
   - [ ] Analytics integration
   - [ ] Multi-language support

4. **Production Hardening**
   - [ ] Rate limiting
   - [ ] Input validation
   - [ ] Content filtering
   - [ ] Error recovery
   - [ ] Performance monitoring

---

## Additional Resources

### Documentation

- [Amplify AI Kit Docs](https://docs.amplify.aws/react/ai/set-up-ai/)
- [AIConversation Component API](https://ui.docs.amplify.aws/react/connected-components/ai/conversation)
- [Bedrock API Reference](https://docs.aws.amazon.com/bedrock/latest/APIReference/welcome.html)
- [AppSync Resolver Mapping](https://docs.aws.amazon.com/appsync/latest/devguide/resolver-mapping-template-reference.html)

### Example Projects

- [Amplify AI Kit Examples](https://github.com/aws-amplify/amplify-ui/tree/main/examples/react-ai)
- [Bedrock Knowledge Base RAG](https://github.com/aws-samples/amazon-bedrock-samples/tree/main/knowledge-bases)

### Support

- **Amplify Discord**: https://discord.gg/amplify
- **AWS Support**: Create case in AWS Console
- **GitHub Issues**: https://github.com/aws-amplify/amplify-ui/issues

---

## Summary

This guide walked through configuring the Amplify AI Kit backend to enable full chat functionality:

1. ✅ Defined GraphQL schema for conversations and messages
2. ✅ Created Lambda resolver to handle chat queries
3. ✅ Connected Lambda to Bedrock Knowledge Base and AI models
4. ✅ Restored AIConversation component in web component
5. ✅ Tested end-to-end chat flow

**Estimated Time:** 2-4 hours for experienced AWS developers

**Complexity:** Medium (requires GraphQL, Lambda, and Bedrock knowledge)

**Status After Completion:** Fully functional AI chat with RAG capabilities ✅

Good luck! 🚀
