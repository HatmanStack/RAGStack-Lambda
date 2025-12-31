export const updateConfiguration = `
  mutation UpdateConfiguration($customConfig: AWSJSON!) {
    updateConfiguration(customConfig: $customConfig)
  }
`;
