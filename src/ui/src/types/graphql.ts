/**
 * Type helpers for AWS Amplify GraphQL responses.
 *
 * Amplify's client.graphql() returns a union type that includes subscriptions,
 * making it awkward to access .data and .errors on query/mutation responses.
 * These types provide cleaner access patterns.
 */

/**
 * Standard GraphQL response shape for queries and mutations.
 */
export type GqlResponse<T = Record<string, unknown>> = {
  data?: T;
  errors?: Array<{ message: string }>;
};

/**
 * Type assertion helper - use after await client.graphql()
 * Example: const response = await client.graphql({...}) as GqlResponse;
 */
export type { GqlResponse as GraphQLQueryResponse };
