/**
 * Typed wrappers for Amplify GraphQL operations.
 *
 * Consolidates the `as unknown as string` and `as any` casts needed
 * because graphql-tag returns DocumentNode but Amplify expects string,
 * and subscription types lack .subscribe() in the Amplify type defs.
 */
import { type DocumentNode } from 'graphql';

/**
 * Cast a graphql-tag DocumentNode to the string type Amplify expects.
 * Amplify internally calls `print()` on DocumentNode objects, so this
 * is safe at runtime despite the type mismatch.
 */
export function gqlQuery(doc: DocumentNode): string {
  return doc as unknown as string;
}

/** Minimal subscription shape returned by Amplify's graphql() for subscriptions. */
export interface GqlSubscription<T = Record<string, unknown>> {
  subscribe(observer: {
    next: (value: { data?: T }) => void;
    error: (err: Error) => void;
  }): { unsubscribe: () => void };
}

/**
 * Subscribe to an Amplify GraphQL subscription.
 * Wraps the untyped return from `client.graphql()` with proper types.
 */
export function gqlSubscribe<T>(
  client: { graphql: (options: { query: string }) => unknown },
  doc: DocumentNode,
): GqlSubscription<T> {
  return client.graphql({ query: gqlQuery(doc) }) as GqlSubscription<T>;
}
