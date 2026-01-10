/**
 * Template for SAM API Configuration (CI/Development)
 *
 * This file provides stub values for TypeScript compilation in CI.
 * The actual amplify-config.generated.ts is created during build
 * by scripts/inject-amplify-config.js with real endpoint values.
 */

/**
 * SAM Stack GraphQL API endpoint and API key
 * Used by ChatInterface to query the knowledge base
 */
declare const SAM_GRAPHQL_ENDPOINT: string;
declare const SAM_GRAPHQL_API_KEY: string;

/**
 * Theme configuration embedded at build time (fallback defaults)
 *
 * These defaults are used if runtime theme fetching fails.
 * Can be overridden per-instance using attributes on <ragstack-chat>.
 */
export const THEME_CONFIG = {
  "themeOverrides": {}
} as const;
