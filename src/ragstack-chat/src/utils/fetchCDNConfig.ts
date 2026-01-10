/**
 * Fetch CDN configuration for API discovery
 *
 * At runtime, the web component fetches config.json from the same CDN origin
 * to discover the API endpoint and Identity Pool ID. This enables configuration
 * without rebuilding the web component.
 */

interface CDNConfig {
  apiEndpoint: string;
  identityPoolId: string;
  region: string;
}

// Cache the CDN config to avoid refetching on every request
let cachedCDNConfig: CDNConfig | null = null;

/**
 * Fetch CDN config.json to get API endpoint and Identity Pool ID
 * Uses the script's origin to construct the config URL
 */
export async function fetchCDNConfig(): Promise<CDNConfig | null> {
  if (cachedCDNConfig) {
    return cachedCDNConfig;
  }

  try {
    // Get the base URL from the current script's location
    const scripts = document.querySelectorAll('script[src*="ragstack-chat"]');
    let baseUrl = '';

    if (scripts.length > 0) {
      const scriptSrc = (scripts[0] as HTMLScriptElement).src;
      baseUrl = scriptSrc.substring(0, scriptSrc.lastIndexOf('/'));
    }

    const configUrl = baseUrl ? `${baseUrl}/config.json` : '/config.json';

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    const response = await fetch(configUrl, {
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      return null;
    }

    const config = await response.json();
    cachedCDNConfig = config;
    return config;
  } catch {
    return null;
  }
}
