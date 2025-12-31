export const regenerateApiKey = /* GraphQL */ `
  mutation RegenerateApiKey {
    regenerateApiKey {
      apiKey
      id
      expires
      error
    }
  }
`;
