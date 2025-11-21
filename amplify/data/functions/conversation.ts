/**
 * Get chat configuration from ConfigurationTable with caching
 *
 * Merges 'Default' and 'Custom' configuration items.
 * Custom values override Default values.
 */
export async function getChatConfig(): Promise<ChatConfig> {
  // Return cached config if still valid
  const now = Date.now();
  if (cachedConfig && (now - cacheTime < CACHE_TTL_MS)) {
    console.log('Using cached config');
    return cachedConfig;
  }

  console.log('Fetching config from DynamoDB...');

  const dynamodb = new DynamoDBClient({ region: process.env.AWS_REGION! });

  try {
    // Fetch both Default and Custom configuration in parallel
    const [defaultResult, customResult] = await Promise.all([
      dynamodb.send(
        new GetItemCommand({
          TableName: process.env.CONFIGURATION_TABLE_NAME!,
          Key: { Configuration: { S: 'Default' } },
        })
      ),
      dynamodb.send(
        new GetItemCommand({
          TableName: process.env.CONFIGURATION_TABLE_NAME!,
          Key: { Configuration: { S: 'Custom' } },
        })
      )
    ]);

    if (!defaultResult.Item) {
      throw new Error('Default configuration not found in ConfigurationTable');
    }

    const defaultItem = defaultResult.Item;
    const customItem = customResult.Item || {};

    // Helper to get value from either Custom or Default, prioritizing Custom
    const getVal = (key: string, type: 'S' | 'N' | 'BOOL') => {
      if (customItem[key] && customItem[key][type] !== undefined) {
        return customItem[key][type];
      }
      if (defaultItem[key] && defaultItem[key][type] !== undefined) {
        return defaultItem[key][type];
      }
      return undefined;
    };

    // Parse merged config
    const config: ChatConfig = {
      requireAuth: getVal('chat_require_auth', 'BOOL') ?? false,
      primaryModel: getVal('chat_primary_model', 'S') ?? 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
      fallbackModel: getVal('chat_fallback_model', 'S') ?? 'us.amazon.nova-micro-v1:0',
      globalQuotaDaily: parseInt(getVal('chat_global_quota_daily', 'N') ?? '10000'),
      perUserQuotaDaily: parseInt(getVal('chat_per_user_quota_daily', 'N') ?? '100'),
      allowDocumentAccess: getVal('chat_allow_document_access', 'BOOL') ?? false,
    };

    // Update cache
    cachedConfig = config;
    cacheTime = now;

    console.log('Config loaded:', config);
    return config;

  } catch (error) {
    console.error('Error fetching config:', error);
    throw new Error(`Failed to load configuration: ${error}`);
  }
}
