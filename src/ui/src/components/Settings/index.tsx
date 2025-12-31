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
import type { GqlResponse } from '../../types/graphql';

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
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

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
  const [apiKeyError, setApiKeyError] = useState(null);
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

  const saveConfiguration = async (values) => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      // Only save values that differ from current merged config (Default + Custom)
      const currentMergedValues = { ...defaultConfig, ...customConfig };
      const changedValues = {};
      Object.keys(values).forEach(key => {
        const currentValue = currentMergedValues[key];
        const newValue = values[key];
        const isDifferent = newValue !== currentValue;
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

    } catch (err) {
      console.error('[Settings] Error saving configuration:', err);
      console.error('[Settings] Error details:', err.errors || err.message || err);
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
      const handleNumberChange = (newValue) => {
        const parsedValue = parseInt(newValue, 10);
        setFormValues({ ...formValues, [key]: parsedValue });

        // Validate quota fields
        if (key.includes('quota')) {
          const validation = validateQuota(parsedValue);
          if (!validation.valid) {
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
          if (!validation.valid) {
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

      <Container header={<Header variant="h2">Public Access</Header>}>
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
      </Container>

      <Container header={<Header variant="h2">Runtime Configuration</Header>}>
        <SpaceBetween size="l">
          {schema.properties &&
            Object.entries(schema.properties)
              .filter(([key]) => !key.includes('theme'))
              .sort((a, b) => (a[1].order || 999) - (b[1].order || 999))
              .map(([key, property]) => (
                <React.Fragment key={key}>
                  {renderField(key, property)}
                </React.Fragment>
              ))}
        </SpaceBetween>
      </Container>

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
