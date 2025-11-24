/**
 * Fetch theme configuration from the Settings API
 *
 * This utility automatically fetches theme settings configured in the
 * Settings UI (stored in DynamoDB) and returns them for the web component.
 */

import { generateClient } from 'aws-amplify/api';

export interface ThemeConfig {
  themePreset: 'light' | 'dark' | 'brand';
  themeOverrides?: {
    primaryColor?: string;
    fontFamily?: string;
    spacing?: 'compact' | 'comfortable' | 'spacious';
  };
}

const GET_CONFIG_QUERY = `
  query GetConfiguration {
    getConfiguration {
      Schema
      Default
      Custom
    }
  }
`;

/**
 * Fetch theme configuration from the GraphQL API
 *
 * @returns Promise<ThemeConfig | null> - Theme config or null if fetch fails
 */
export async function fetchThemeConfig(): Promise<ThemeConfig | null> {
  try {
    console.log('[ThemeConfig] Fetching configuration from API...');

    const client = generateClient();
    const response = await client.graphql({
      query: GET_CONFIG_QUERY,
    });

    // Parse the response
    const configData = response.data.getConfiguration;
    const defaultConfig = JSON.parse(configData.Default);
    const customConfig = JSON.parse(configData.Custom || '{}');

    // Merge custom over default (same logic as Settings UI)
    const mergedConfig = { ...defaultConfig, ...customConfig };

    console.log('[ThemeConfig] Configuration loaded:', {
      preset: mergedConfig.chat_theme_preset,
      hasOverrides: !!mergedConfig.chat_theme_overrides,
    });

    return {
      themePreset: mergedConfig.chat_theme_preset || 'light',
      themeOverrides: mergedConfig.chat_theme_overrides || {},
    };
  } catch (err) {
    console.warn('[ThemeConfig] Failed to fetch theme configuration:', err);
    console.warn('[ThemeConfig] Falling back to default theme');
    return null;
  }
}
