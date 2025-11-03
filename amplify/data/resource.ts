import { defineData, defineFunction } from '@aws-amplify/backend';
import * as path from 'path';

// Define the source extraction tool that Bedrock will call
export const extractSourcesTool = defineFunction({
  name: 'extractSourcesTool',
  entry: path.join(__dirname, 'functions', 'extractSources.ts'),
});

export const data = defineData({
  routes: {
    // Main conversation route for chat
    conversation: {
      // Model: us.anthropic.claude-haiku-4-5-20251001-v1:0 (Haiku)
      // This matches the default model in SAM's ConfigurationTable (chat_model_id)
      // When users change the model in Settings UI, the SAM system uses that configuration.
      // Future enhancement (Phase 2+): Dynamic model selection via custom Lambda handler
      // that reads from ConfigurationTable and routes to different conversation instances
      model: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',

      // System prompt - tells the model how to behave
      systemPrompt: `You are a helpful assistant that answers questions about documents in the knowledge base.

When answering:
1. Base your answers on information from the knowledge base
2. If asked about something not in the knowledge base, say so
3. Be concise and clear
4. If multiple sources could answer the question, cite all of them

You have access to a knowledge base containing important documents. Use it to provide accurate, sourced answers.`,

      // Tools that Bedrock can call - includes source extraction
      tools: [extractSourcesTool],

      // NOTE: Knowledge Base configuration will be added via environment variables
      // See the deployment section for how to pass KNOWLEDGE_BASE_ID
    },
  },

  // Who can access the API
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',  // Users must be logged in
  },
});

// Export for use in backend.ts
export default data;
