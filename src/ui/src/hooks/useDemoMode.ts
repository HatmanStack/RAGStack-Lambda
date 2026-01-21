import { useState, useEffect, useCallback } from 'react';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../graphql/queries/getConfiguration';

interface DemoModeState {
  isEnabled: boolean;
  uploadLimit: number;
  chatLimit: number;
  loading: boolean;
  error: string | null;
}

interface ConfigurationResponse {
  getConfiguration: {
    Schema: string;
    Default: string;
    Custom: string;
  };
}

const client = generateClient();

/**
 * Hook to detect and manage demo mode state.
 *
 * Demo mode is enabled via deployment (DEMO_MODE=true env var) and provides:
 * - Rate limits: configurable uploads/day and chat messages/day
 * - Disabled features: reindex, reprocess, delete
 */
export const useDemoMode = (): DemoModeState & { refresh: () => Promise<void> } => {
  const [state, setState] = useState<DemoModeState>({
    isEnabled: false,
    uploadLimit: 5,
    chatLimit: 30,
    loading: true,
    error: null,
  });

  const loadConfig = useCallback(async () => {
    try {
      const response = await client.graphql({
        query: getConfiguration,
      }) as { data: ConfigurationResponse };

      const config = response.data?.getConfiguration;
      if (!config) {
        throw new Error('Failed to load configuration');
      }

      // Parse config - Default and Custom are JSON strings
      const defaultConfig = JSON.parse(config.Default || '{}');
      const customConfig = JSON.parse(config.Custom || '{}');

      // Merge custom over default (custom takes precedence)
      const merged = { ...defaultConfig, ...customConfig };

      setState({
        isEnabled: merged.demo_mode_enabled === true,
        uploadLimit: merged.demo_upload_quota_daily ?? 5,
        chatLimit: merged.demo_chat_quota_daily ?? 30,
        loading: false,
        error: null,
      });
    } catch (err) {
      console.error('Failed to load demo mode config:', err);
      setState(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Failed to load configuration',
      }));
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  return {
    ...state,
    refresh: loadConfig,
  };
};

export default useDemoMode;
