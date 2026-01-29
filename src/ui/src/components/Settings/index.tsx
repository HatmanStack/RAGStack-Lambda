/**
 * Settings Component
 *
 * IMPLEMENTATION NOTE: Schema-Driven Approach
 * -------------------------------------------
 * This implementation deviates from the Phase 5 specification, which called for
 * a dedicated ChatSettings component. Instead, we extended the existing schema-driven
 * Settings component to handle chat configuration fields.
 *
 * Rationale for deviation:
 * 1. **Consistency**: Matches existing OCR settings pattern
 * 2. **DRY**: Leverages existing renderField() logic instead of duplicating
 * 3. **Maintainability**: Single source of truth (ConfigurationTable schema)
 * 4. **Simplicity**: ~200 lines of code vs ~500+ for dedicated component
 * 5. **Scalability**: Easy to add new chat fields without code changes
 *
 * The schema-driven approach automatically renders form fields from the
 * ConfigurationTable schema definition in publish.py:
 * - Boolean → Toggle
 * - Number → Input with validation
 * - Enum → Select dropdown
 * - Object → Inline nested inputs
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  FormField,
  Select,
  Button,
  Alert,
  Box,
  Toggle,
  Input,
  ExpandableSection,
  CopyToClipboard,
  ColumnLayout,
  Popover,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { getApiKey } from '../../graphql/queries/getApiKey';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import { regenerateApiKey } from '../../graphql/mutations/regenerateApiKey';
import {
  validateQuota,
  validateBudgetThreshold,
} from '../../utils/validation';
import { ReindexSection } from './ReindexSection';
import { useDemoMode } from '../../hooks/useDemoMode';
import type { GqlResponse } from '../../types/graphql';
import { MetadataKeyInput } from './MetadataKeyInput';
import { MetadataPanel } from '../Search/MetadataPanel';

interface ConfigResponse {
  Schema: string;
  Default: string;
  Custom: string;
}

interface ApiKeyResponse {
  apiKey: string;
  expires: string;
  error?: string;
}

interface SchemaProperty {
  type?: string;
  enum?: string[];
  description?: string;
  order?: number;
  dependsOn?: { field: string; value: unknown };
  properties?: Record<string, SchemaProperty>;
}

export function Settings() {
  // State for loading and errors
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Demo mode state
  const { isEnabled: isDemoMode, uploadLimit, chatLimit } = useDemoMode();

  // State for configuration data
  const [schema, setSchema] = useState<Record<string, unknown>>({});
  const [defaultConfig, setDefaultConfig] = useState<Record<string, unknown>>({});
  const [customConfig, setCustomConfig] = useState<Record<string, unknown>>({});
  const [formValues, setFormValues] = useState<Record<string, unknown>>({});

  // State for validation errors
  const [validationErrors, setValidationErrors] = useState<Record<string, string>>({});

  // State for API key management
  const [apiKeyData, setApiKeyData] = useState<{ apiKey: string; expires: string } | null>(null);
  const [apiKeyLoading, setApiKeyLoading] = useState(false);
  const [apiKeyError, setApiKeyError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Memoize the client to prevent recreation on every render
  const client = React.useMemo(() => generateClient(), []);

  const loadConfiguration = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await client.graphql({ query: getConfiguration }) as GqlResponse;
      const config = response.data?.getConfiguration as ConfigResponse | undefined;

      if (!config) {
        throw new Error('Configuration not found');
      }

      // Parse JSON strings
      const parsedSchema = JSON.parse(config.Schema);
      const parsedDefault = JSON.parse(config.Default);
      const parsedCustom = JSON.parse(config.Custom || '{}');

      setSchema(parsedSchema);
      setDefaultConfig(parsedDefault);
      setCustomConfig(parsedCustom);

      // Initialize form with custom values overriding defaults
      const initialValues = { ...parsedDefault, ...parsedCustom };
      setFormValues(initialValues);

      setLoading(false);
    } catch (err) {
      console.error('Error loading configuration:', err);
      setError('Failed to load configuration. Please try again.');
      setLoading(false);
    }
  }, [client]);

  const loadApiKey = useCallback(async () => {
    try {
      setApiKeyLoading(true);
      setApiKeyError(null);

      const response = await client.graphql({ query: getApiKey }) as GqlResponse;
      const data = response.data?.getApiKey as ApiKeyResponse | undefined;

      if (data?.error) {
        setApiKeyError(data.error);
      } else if (data) {
        setApiKeyData(data);
      }
    } catch (err) {
      console.error('Error loading API key:', err);
      setApiKeyError('Failed to load API key');
    } finally {
      setApiKeyLoading(false);
    }
  }, [client]);

  const handleRegenerateApiKey = async () => {
    if (!window.confirm('Are you sure you want to regenerate the API key? The old key will stop working immediately.')) {
      return;
    }

    try {
      setRegenerating(true);
      setApiKeyError(null);

      const response = await client.graphql({ query: regenerateApiKey }) as GqlResponse;
      const data = response.data?.regenerateApiKey as ApiKeyResponse | undefined;

      if (data?.error) {
        setApiKeyError(data.error);
      } else if (data) {
        setApiKeyData(data);
        setShowApiKey(true); // Show the new key
      }
    } catch (err) {
      console.error('Error regenerating API key:', err);
      setApiKeyError('Failed to regenerate API key');
    } finally {
      setRegenerating(false);
    }
  };

  // Load configuration and API key on mount
  useEffect(() => {
    loadConfiguration();
    loadApiKey();
  }, [loadConfiguration, loadApiKey]);

  const handleSave = async () => {
    try {
      // Block save if there are validation errors
      if (Object.keys(validationErrors).length > 0) {
        console.error('[Settings] Blocked by validation errors:', validationErrors);
        setError('Please fix validation errors before saving');
        return;
      }

      await saveConfiguration(formValues);
    } catch (err) {
      console.error('[Settings] Error in handleSave:', err);
      setError('Failed to save configuration. Please try again.');
    }
  };

  const saveConfiguration = async (values: Record<string, unknown>) => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      // Only save values that differ from current merged config (Default + Custom)
      const currentMergedValues = { ...defaultConfig, ...customConfig };
      const changedValues: Record<string, unknown> = {};
      Object.keys(values).forEach(key => {
        const currentValue = currentMergedValues[key];
        const newValue = values[key];
        // Use JSON.stringify for array/object comparison
        const isDifferent = Array.isArray(newValue) || typeof newValue === 'object'
          ? JSON.stringify(newValue) !== JSON.stringify(currentValue)
          : newValue !== currentValue;
        if (isDifferent) {
          changedValues[key] = newValue;
        }
      });

      await client.graphql({
        query: updateConfiguration,
        variables: {
          customConfig: JSON.stringify(changedValues)
        }
      });

      setSuccess(true);
      setSaving(false);

      // Reload configuration
      setTimeout(() => {
        loadConfiguration();
        setSuccess(false);
      }, 2000);

    } catch (err: unknown) {
      console.error('[Settings] Error saving configuration:', err);
      const errorObj = err as { errors?: unknown; message?: string };
      console.error('[Settings] Error details:', errorObj.errors || errorObj.message || err);
      setError('Failed to save configuration. Please try again.');
      setSaving(false);
    }
  };

  const handleReset = () => {
    // Reset form to current saved state
    const currentValues = { ...defaultConfig, ...customConfig };
    setFormValues(currentValues);
    setSuccess(false);
    setError(null);
  };

  const renderField = (key: string, property: SchemaProperty) => {
    if (!property) return null;

    const value = formValues[key];
    const isCustomized = Object.prototype.hasOwnProperty.call(customConfig, key);
    const validationError = validationErrors[key];

    // Skip chat_cdn_url - shown in Chat tab instead
    if (key === 'chat_cdn_url') {
      return null;
    }

    // Skip chat_allow_document_access - rendered separately in API Key section
    if (key === 'chat_allow_document_access') {
      return null;
    }

    // Skip chat_require_auth - handled by public_access_chat toggle
    if (key === 'chat_require_auth') {
      return null;
    }

    // Skip public_access_* fields - rendered separately in Public Access section
    if (key.startsWith('public_access_')) {
      return null;
    }

    // Skip metadata_* fields - rendered separately in Metadata Extraction section
    if (key.startsWith('metadata_')) {
      return null;
    }

    // Skip filter_generation_* and multislice_* - rendered separately in Metadata Query section
    if (key.startsWith('filter_generation_') || key.startsWith('multislice_')) {
      return null;
    }

    // Handle conditional visibility (dependsOn)
    if (property.dependsOn) {
      const depField = property.dependsOn.field;
      const depValue = property.dependsOn.value;
      const currentDepValue = formValues[depField];

      if (currentDepValue !== depValue) {
        return null; // Hide this field
      }
    }

    // Render dropdown for enum fields
    if (property.enum && Array.isArray(property.enum)) {
      return (
        <FormField
          label={property.description || key}
          description={isCustomized ? 'Customized from default' : ''}
          errorText={validationError}
        >
          <Select
            selectedOption={{ label: String(value || ''), value: String(value || '') }}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, [key]: detail.selectedOption.value });
              // Clear validation error on change
              if (validationErrors[key]) {
                const newErrors = { ...validationErrors };
                delete newErrors[key];
                setValidationErrors(newErrors);
              }
            }}
            options={property.enum.map(v => ({ label: v, value: v, key: v }))}
          />
        </FormField>
      );
    }

    // Render toggle for boolean fields
    if (property.type === 'boolean') {
      return (
        <FormField
          label={property.description || key}
          description={isCustomized ? 'Customized from default' : ''}
        >
          <Toggle
            checked={value === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, [key]: detail.checked });
            }}
          >
            {value ? 'Enabled' : 'Disabled'}
          </Toggle>
        </FormField>
      );
    }

    // Render input for number fields
    if (property.type === 'number') {
      const handleNumberChange = (newValue: string) => {
        const parsedValue = parseInt(newValue, 10);
        setFormValues({ ...formValues, [key]: parsedValue });

        // Validate quota fields
        if (key.includes('quota')) {
          const validation = validateQuota(parsedValue);
          if (!validation.valid && validation.error) {
            setValidationErrors({ ...validationErrors, [key]: validation.error });
          } else {
            const newErrors = { ...validationErrors };
            delete newErrors[key];
            setValidationErrors(newErrors);
          }
        }

        // Validate budget threshold fields
        if (key === 'budget_alert_threshold') {
          const validation = validateBudgetThreshold(parsedValue);
          if (!validation.valid && validation.error) {
            setValidationErrors({ ...validationErrors, [key]: validation.error });
          } else {
            const newErrors = { ...validationErrors };
            delete newErrors[key];
            setValidationErrors(newErrors);
          }
        }
      };

      return (
        <FormField
          label={property.description || key}
          description={isCustomized ? 'Customized from default' : ''}
          errorText={validationError}
        >
          <Input
            type="number"
            value={String(value || 0)}
            onChange={({ detail }) => handleNumberChange(detail.value)}
            invalid={!!validationError}
          />
        </FormField>
      );
    }

    // Render nested inputs for object fields
    if (property.type === 'object' && property.properties) {
      return renderObjectField(key, property, (value as Record<string, unknown>) || {});
    }

    return null;
  };

  const renderObjectField = (parentKey: string, property: SchemaProperty, value: Record<string, unknown>) => {
    const handleNestedChange = (nestedKey: string, nestedValue: unknown) => {
      const updatedObject = { ...value, [nestedKey]: nestedValue };
      setFormValues({ ...formValues, [parentKey]: updatedObject });
    };

    // Render fields directly without wrapper for theme overrides
    return (
      <>
        {validationErrors[parentKey] && (
          <Alert type="error">
            {validationErrors[parentKey]}
          </Alert>
        )}

        {Object.entries(property.properties || {}).map(([nestedKey, nestedProp]) => {
          const nestedValue = (value[nestedKey] as string) || '';

          // Render nested enum as dropdown
          if (nestedProp.enum) {
            return (
              <FormField
                key={nestedKey}
                label={nestedKey}
                description={nestedProp.description}
              >
                <Select
                  selectedOption={{ label: nestedValue, value: nestedValue }}
                  onChange={({ detail }) => handleNestedChange(nestedKey, detail.selectedOption.value)}
                  options={nestedProp.enum.map(v => ({ label: v, value: v, key: v }))}
                />
              </FormField>
            );
          }

          // Render nested string as input
          return (
            <FormField
              key={nestedKey}
              label={nestedKey}
              description={nestedProp.description}
            >
              <Input
                type="text"
                value={nestedValue}
                onChange={({ detail }) => handleNestedChange(nestedKey, detail.value)}
                placeholder={
                  nestedKey === 'primaryColor' ? '#0073bb' :
                  nestedKey === 'fontFamily' ? 'Inter, system-ui, sans-serif' :
                  ''
                }
              />
            </FormField>
          );
        })}
      </>
    );
  };

  if (loading) {
    return (
      <Container>
        <Box textAlign="center" padding="xxl">
          Loading configuration...
        </Box>
      </Container>
    );
  }

  return (
    <SpaceBetween size="l">
      <Header variant="h1">Settings</Header>

      {error && (
        <Alert type="error" dismissible onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      {success && (
        <Alert type="success" dismissible onDismiss={() => setSuccess(false)}>
          Configuration saved successfully
        </Alert>
      )}

      {isDemoMode && (
        <Alert type="info" header="Demo Mode Active">
          <SpaceBetween size="xs">
            <Box>This deployment is running in Demo Mode with the following restrictions:</Box>
            <Box>
              <ul style={{ margin: 0, paddingLeft: '20px' }}>
                <li><strong>Uploads:</strong> {uploadLimit} per day, max 10 MB per file</li>
                <li><strong>Chat messages:</strong> {chatLimit} per day</li>
                <li><strong>Disabled features:</strong> Reindex All, Reprocess, Delete</li>
              </ul>
            </Box>
          </SpaceBetween>
        </Alert>
      )}

      <Container header={<Header variant="h2">API Key</Header>}>
        <SpaceBetween size="m">
          {apiKeyError && (
            <Alert type="error" dismissible onDismiss={() => setApiKeyError(null)}>
              {apiKeyError}
            </Alert>
          )}

          {apiKeyLoading ? (
            <Box>Loading API key...</Box>
          ) : apiKeyData ? (
            <SpaceBetween size="s">
              <FormField label="API Key">
                <SpaceBetween direction="horizontal" size="xs">
                  <Input
                    type={showApiKey ? 'text' : 'password'}
                    value={apiKeyData.apiKey}
                    readOnly
                  />
                  <Button
                    iconName={showApiKey ? 'unlocked' : 'lock-private'}
                    variant="icon"
                    onClick={() => setShowApiKey(!showApiKey)}
                    ariaLabel={showApiKey ? 'Hide API key' : 'Show API key'}
                  />
                  <CopyToClipboard
                    textToCopy={apiKeyData.apiKey}
                    copyButtonText="Copy"
                    copySuccessText="Copied!"
                    copyErrorText="Failed to copy"
                    variant="icon"
                  />
                </SpaceBetween>
              </FormField>

              <Box variant="small" color="text-body-secondary">
                Expires: {new Date(apiKeyData.expires).toLocaleDateString()}
              </Box>

              <Button
                onClick={handleRegenerateApiKey}
                loading={regenerating}
                iconName="refresh"
              >
                Regenerate API Key
              </Button>
            </SpaceBetween>
          ) : (
            <Box>No API key available</Box>
          )}

          <FormField
            label="Allow Document Downloads"
            description="Let users download original source documents via chat citations"
          >
            <Toggle
              checked={formValues.chat_allow_document_access === true}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, chat_allow_document_access: detail.checked });
              }}
            >
              {formValues.chat_allow_document_access ? 'Enabled' : 'Disabled'}
            </Toggle>
          </FormField>

          <ExpandableSection
            headerText="MCP Server Setup"
            variant="footer"
          >
            <SpaceBetween size="s">
              <Box variant="small" color="text-body-secondary">
                Connect Claude Desktop, Cursor, VS Code, or Amazon Q CLI to your knowledge base.
              </Box>

              {apiKeyData && (
                <>
                  <Box>
                    <code
                      style={{
                        display: 'block',
                        whiteSpace: 'pre-wrap',
                        padding: '12px',
                        background: '#1a1a2e',
                        color: '#e6e6e6',
                        borderRadius: '6px',
                        fontFamily: "'Fira Code', 'Monaco', monospace",
                        fontSize: '12px',
                        lineHeight: '1.5',
                      }}
                    >
{`{
  "ragstack-kb": {
    "command": "uvx",
    "args": ["ragstack-mcp"],
    "env": {
      "RAGSTACK_GRAPHQL_ENDPOINT": "${import.meta.env.VITE_GRAPHQL_URL || 'YOUR_ENDPOINT'}",
      "RAGSTACK_API_KEY": "${apiKeyData.apiKey}"
    }
  }
}`}
                    </code>
                  </Box>
                  <CopyToClipboard
                    textToCopy={`{
  "ragstack-kb": {
    "command": "uvx",
    "args": ["ragstack-mcp"],
    "env": {
      "RAGSTACK_GRAPHQL_ENDPOINT": "${import.meta.env.VITE_GRAPHQL_URL || 'YOUR_ENDPOINT'}",
      "RAGSTACK_API_KEY": "${apiKeyData.apiKey}"
    }
  }
}`}
                    copyButtonText="Copy"
                    copySuccessText="Copied!"
                    copyErrorText="Failed to copy"
                    variant="icon"
                  />
                </>
              )}

              <Box variant="small" color="text-body-secondary">
                <strong>Config locations:</strong> Claude Desktop: ~/Library/Application Support/Claude/claude_desktop_config.json •
                Amazon Q: ~/.aws/amazonq/mcp.json • Cursor: Settings → MCP Servers
              </Box>
            </SpaceBetween>
          </ExpandableSection>
        </SpaceBetween>
      </Container>

      <ExpandableSection
        variant="container"
        headerText="Public Access"
        headerInfo={
          <Popover
            header="About Public Access"
            content="Control which features are accessible without authentication. When enabled, users can access these features without logging in. Useful for public-facing demos or open knowledge bases."
            triggerType="custom"
            dismissButton={false}
            position="right"
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="About Public Access" />
            </span>
          </Popover>
        }
        defaultExpanded={false}
      >
        <ColumnLayout columns={3} variant="text-grid">
          <Toggle
            checked={formValues.public_access_chat === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, public_access_chat: detail.checked });
            }}
          >
            Chat Queries
          </Toggle>
          <Toggle
            checked={formValues.public_access_search === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, public_access_search: detail.checked });
            }}
          >
            Search API
          </Toggle>
          <Toggle
            checked={formValues.public_access_upload === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, public_access_upload: detail.checked });
            }}
          >
            Document Uploads
          </Toggle>
          <Toggle
            checked={formValues.public_access_image_upload === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, public_access_image_upload: detail.checked });
            }}
          >
            Image Uploads
          </Toggle>
          <Toggle
            checked={formValues.public_access_scrape === true}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, public_access_scrape: detail.checked });
            }}
          >
            Web Scraping
          </Toggle>
        </ColumnLayout>
      </ExpandableSection>

      <ExpandableSection
        variant="container"
        headerText="Metadata Extraction"
        headerInfo={
          <Popover
            header="About Metadata Extraction"
            content="LLM-based metadata extraction analyzes documents during upload to generate searchable metadata fields. Auto mode lets the LLM decide which keys to extract, while Manual mode uses your specified key list. Reindex your KB without having to reprocess."
            triggerType="custom"
            dismissButton={false}
            position="right"
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="About Metadata Extraction" />
            </span>
          </Popover>
        }
        defaultExpanded={false}
      >
        <SpaceBetween size="m">
          <FormField
            label="Enable Metadata Extraction"
            description="Extract searchable metadata from documents during ingestion"
          >
            <Toggle
              checked={formValues.metadata_extraction_enabled === true}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, metadata_extraction_enabled: detail.checked });
              }}
            >
              {formValues.metadata_extraction_enabled ? 'Enabled' : 'Disabled'}
            </Toggle>
          </FormField>

          <FormField
            label="Extraction Model"
            description="Lightweight model for cost-efficient extraction"
          >
            <Select
              selectedOption={{
                label: String(formValues.metadata_extraction_model || ''),
                value: String(formValues.metadata_extraction_model || ''),
              }}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, metadata_extraction_model: detail.selectedOption.value });
              }}
              options={
                ((schema as { properties?: Record<string, SchemaProperty> }).properties?.metadata_extraction_model?.enum || [])
                  .map(v => ({ label: v, value: v }))
              }
              disabled={formValues.metadata_extraction_enabled !== true}
            />
          </FormField>

          <FormField
            label="Maximum Keys"
            description="Maximum metadata fields to extract per document"
          >
            <Input
              type="number"
              value={String(formValues.metadata_max_keys || 8)}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, metadata_max_keys: parseInt(detail.value, 10) || 8 });
              }}
              disabled={formValues.metadata_extraction_enabled !== true}
            />
          </FormField>

          <FormField
            label="Extraction Mode"
            description="Auto lets LLM decide keys, Manual uses your specified list"
            info={
              <Popover
                header="About Extraction Mode"
                content="Auto mode: LLM analyzes each document and decides which keys to extract. Manual mode: Only extracts the specific keys you specify. Changes only affect newly uploaded documents - to update existing documents, use the Reindex feature below."
                triggerType="custom"
                dismissButton={false}
                position="right"
                size="medium"
              >
                <span style={{ position: 'relative', top: '-2px' }}>
                  <Button variant="inline-icon" iconName="status-info" ariaLabel="About Extraction Mode" />
                </span>
              </Popover>
            }
          >
            <Select
              selectedOption={{
                label: formValues.metadata_extraction_mode === 'manual' ? 'Manual' : 'Auto',
                value: String(formValues.metadata_extraction_mode || 'auto'),
              }}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, metadata_extraction_mode: detail.selectedOption.value });
              }}
              options={[
                { label: 'Auto', value: 'auto', description: 'LLM decides which keys to extract' },
                { label: 'Manual', value: 'manual', description: 'Use your specified key list' },
              ]}
              disabled={formValues.metadata_extraction_enabled !== true}
            />
          </FormField>

          {formValues.metadata_extraction_mode === 'manual' && (
            <FormField
              label="Keys to Extract"
              description="Metadata keys to extract when in Manual mode. System keys (content_type, media_type, filename) are preserved automatically."
            >
              <MetadataKeyInput
                value={(formValues.metadata_manual_keys as string[]) || []}
                onChange={(keys) => setFormValues({ ...formValues, metadata_manual_keys: keys })}
                disabled={formValues.metadata_extraction_enabled !== true}
              />
            </FormField>
          )}

          {/* Divider */}
          <Box margin={{ top: 'm' }}>
            <hr style={{ border: 'none', borderTop: '1px solid #e9ebed' }} />
          </Box>

          {/* Reindex section */}
          <ReindexSection />
        </SpaceBetween>
      </ExpandableSection>

      <ExpandableSection
        variant="container"
        headerText="Metadata Query"
        headerInfo={
          <Popover
            header="About Metadata Query"
            content="Configure how metadata filters are generated and applied during knowledge base queries. Multi-slice retrieval runs parallel queries with different filters for better recall."
            triggerType="custom"
            dismissButton={false}
            position="right"
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="About Metadata Query" />
            </span>
          </Popover>
        }
        defaultExpanded={false}
      >
        <SpaceBetween size="m">
          <FormField
            label="Enable Filter Generation"
            description="Use LLM to generate metadata filters from natural language queries"
          >
            <Toggle
              checked={formValues.filter_generation_enabled === true}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, filter_generation_enabled: detail.checked });
              }}
            >
              {formValues.filter_generation_enabled ? 'Enabled' : 'Disabled'}
            </Toggle>
          </FormField>

          <FormField
            label="Filter Generation Model"
            description="Lightweight model for cost-efficient filter generation"
          >
            <Select
              selectedOption={{
                label: String(formValues.filter_generation_model || ''),
                value: String(formValues.filter_generation_model || ''),
              }}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, filter_generation_model: detail.selectedOption.value });
              }}
              options={
                ((schema as { properties?: Record<string, SchemaProperty> }).properties?.filter_generation_model?.enum || [])
                  .map(v => ({ label: v, value: v }))
              }
              disabled={formValues.filter_generation_enabled !== true}
            />
          </FormField>

          <FormField
            label="Enable Multi-Slice Retrieval"
            description="Run parallel filtered and unfiltered queries for better recall"
          >
            <Toggle
              checked={formValues.multislice_enabled === true}
              onChange={({ detail }) => {
                setFormValues({ ...formValues, multislice_enabled: detail.checked });
              }}
              disabled={formValues.filter_generation_enabled !== true}
            >
              {formValues.multislice_enabled ? 'Enabled' : 'Disabled'}
            </Toggle>
          </FormField>

          {formValues.multislice_enabled === true && formValues.filter_generation_enabled === true && (
            <>
              <FormField
                label="Number of Slices"
                description="Parallel retrieval slices (2-4)"
              >
                <Input
                  type="number"
                  value={String(formValues.multislice_count || 2)}
                  onChange={({ detail }) => {
                    const val = parseInt(detail.value, 10);
                    if (val >= 2 && val <= 4) {
                      setFormValues({ ...formValues, multislice_count: val });
                    }
                  }}
                />
              </FormField>

              <FormField
                label="Slice Timeout (ms)"
                description="Timeout per slice in milliseconds"
              >
                <Input
                  type="number"
                  value={String(formValues.multislice_timeout_ms || 5000)}
                  onChange={({ detail }) => {
                    setFormValues({ ...formValues, multislice_timeout_ms: parseInt(detail.value, 10) });
                  }}
                />
              </FormField>

              <FormField
                label="Filtered Results Boost"
                description="Score multiplier for results matching metadata filters (1.0 = no boost, 2.0 = double)"
              >
                <Input
                  type="number"
                  step={0.05}
                  value={String(formValues.multislice_filtered_boost ?? 1.25)}
                  onChange={({ detail }) => {
                    const val = parseFloat(detail.value) || 1.25;
                    setFormValues({ ...formValues, multislice_filtered_boost: Math.min(2.0, Math.max(1.0, val)) });
                  }}
                />
              </FormField>
            </>
          )}
        </SpaceBetween>
      </ExpandableSection>

      <MetadataPanel />

      <ExpandableSection
        variant="container"
        headerText="Runtime Configuration"
        headerInfo={
          <Popover
            header="About Runtime Configuration"
            content="Runtime settings that take effect immediately without redeployment. Quotas apply only to the chat API (daily message limits per user). Also includes OCR backend selection and chat model configuration."
            triggerType="custom"
            dismissButton={false}
            position="right"
            size="medium"
          >
            <span style={{ position: 'relative', top: '-2px' }}>
              <Button variant="inline-icon" iconName="status-info" ariaLabel="About Runtime Configuration" />
            </span>
          </Popover>
        }
        defaultExpanded={false}
      >
        <SpaceBetween size="l">
          {(schema as { properties?: Record<string, SchemaProperty> }).properties &&
            Object.entries((schema as { properties: Record<string, SchemaProperty> }).properties)
              .filter(([key]) => !key.includes('theme'))
              .sort((a, b) => ((a[1] as SchemaProperty).order || 999) - ((b[1] as SchemaProperty).order || 999))
              .map(([key, property]) => (
                <React.Fragment key={key}>
                  {renderField(key, property as SchemaProperty)}
                </React.Fragment>
              ))}
        </SpaceBetween>
      </ExpandableSection>

      <Box float="right" padding={{ top: 's' }}>
        <SpaceBetween direction="horizontal" size="xs">
          <Button variant="link" onClick={handleReset} disabled={saving}>
            Reset
          </Button>
          <Button variant="primary" onClick={handleSave} loading={saving}>
            Save changes
          </Button>
        </SpaceBetween>
      </Box>
    </SpaceBetween>
  );
}
