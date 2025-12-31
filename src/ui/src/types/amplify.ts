/**
 * Type utilities for AWS Amplify GraphQL client.
 *
 * The Amplify client.graphql() returns a union type that includes subscriptions,
 * but for queries/mutations we know the exact shape. These helpers provide
 * proper typing for common operations.
 */

import type { GraphQLResult } from 'aws-amplify/api';

/**
 * Extract data from a GraphQL query/mutation response.
 * Use this when you know the response is not a subscription.
 */
export function getGraphQLData<T>(response: unknown): T | null {
  const result = response as GraphQLResult<T>;
  return result.data ?? null;
}

/**
 * Check if response has GraphQL errors.
 */
export function hasGraphQLErrors(response: unknown): boolean {
  const result = response as GraphQLResult<unknown>;
  return Array.isArray(result.errors) && result.errors.length > 0;
}

/**
 * Get GraphQL errors from response.
 */
export function getGraphQLErrors(response: unknown): readonly { message: string }[] {
  const result = response as GraphQLResult<unknown>;
  return result.errors ?? [];
}

/**
 * Type for GraphQL query/mutation response (non-subscription).
 */
export type QueryResult<T> = GraphQLResult<T>;
