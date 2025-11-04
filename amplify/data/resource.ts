import { type ClientSchema, a, defineData, defineFunction } from '@aws-amplify/backend';

const schema = a.schema({
  // Custom types for conversation
  Source: a.customType({
    title: a.string().required(),
    location: a.string(),
    snippet: a.string().required(),
  }),

  ConversationResponse: a.customType({
    content: a.string().required(),
    sources: a.ref('Source').array(),
    modelUsed: a.string(),
  }),

  // Custom query for chat conversation
  conversation: a
    .query()
    .arguments({
      message: a.string().required(),
      conversationId: a.string().required(),
      userId: a.string(),
      userToken: a.string(),
    })
    .returns(a.ref('ConversationResponse'))
    .authorization((allow) => [allow.publicApiKey()])
    .handler(
      a.handler.function(defineFunction({
        entry: './functions/conversation.ts',
        timeoutSeconds: 300,
      }))
    ),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'apiKey',
  },
});

// Export for use in backend.ts
export default data;
