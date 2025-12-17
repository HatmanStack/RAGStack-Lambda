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
 * - Object → ExpandableSection with nested inputs
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  Container,
  Header,
  SpaceBetween,
  Form,
  FormField,
  Select,
  Button,
  Alert,
  Box,
  Toggle,
  Input,
  ExpandableSection,
  CopyToClipboard,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import {
  validateThemeOverrides,
  validateQuota,
} from '../../utils/validation';

export function Settings() {
  // State for loading and errors
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(false);

  // State for configuration data
  const [schema, setSchema] = useState({});
  const [defaultConfig, setDefaultConfig] = useState({});
  const [customConfig, setCustomConfig] = useState({});
  const [formValues, setFormValues] = useState({});

  // State for validation errors
  const [validationErrors, setValidationErrors] = useState({});

  // Memoize the client to prevent recreation on every render
  const client = React.useMemo(() => generateClient(), []);

  const loadConfiguration = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await client.graphql({ query: getConfiguration });
      const config = response.data.getConfiguration;

      // Parse JSON strings
      const parsedSchema = JSON.parse(config.Schema);
      const parsedDefault = JSON.parse(config.Default);
      const parsedCustom = JSON.parse(config.Custom || '{}');

      console.log('[Settings] Config loaded from GraphQL:', {
        defaultKeys: Object.keys(parsedDefault),
        customKeys: Object.keys(parsedCustom),
        default_allowDocAccess: parsedDefault.chat_allow_document_access,
        custom_allowDocAccess: parsedCustom.chat_allow_document_access
      });

      setSchema(parsedSchema);
      setDefaultConfig(parsedDefault);
      setCustomConfig(parsedCustom);

      // Initialize form with custom values overriding defaults
      const initialValues = { ...parsedDefault, ...parsedCustom };
      console.log('[Settings] Initial form values after merge:', {
        chat_allow_document_access: initialValues.chat_allow_document_access,
        chat_theme_preset: initialValues.chat_theme_preset
      });
      setFormValues(initialValues);

      setLoading(false);
    } catch (err) {
      console.error('Error loading configuration:', err);
      setError('Failed to load configuration. Please try again.');
      setLoading(false);
    }
  }, [client]);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
  }, [loadConfiguration]);

  const handleSave = async () => {
    console.log('[Settings] Save clicked');
    console.log('[Settings] Form values:', formValues);
    console.log('[Settings] Default config:', defaultConfig);
    console.log('[Settings] Validation errors:', validationErrors);

    try {
      // Block save if there are validation errors
      if (Object.keys(validationErrors).length > 0) {
        console.error('[Settings] Blocked by validation errors:', validationErrors);
        setError('Please fix validation errors before saving');
        return;
      }

      console.log('[Settings] Calling saveConfiguration...');
      await saveConfiguration(formValues);
    } catch (err) {
      console.error('[Settings] Error in handleSave:', err);
      setError('Failed to save configuration. Please try again.');
    }
  };

  const saveConfiguration = async (values) => {
    try {
      console.log('[Settings] saveConfiguration called with values:', values);
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
        console.log(`[Settings] ${key}: formValue=${newValue}, currentMerged=${currentValue}, different=${isDifferent}`);
        if (isDifferent) {
          changedValues[key] = newValue;
        }
      });

      console.log('[Settings] Changed values to save:', changedValues);
      console.log('[Settings] Changed values JSON:', JSON.stringify(changedValues));

      const response = await client.graphql({
        query: updateConfiguration,
        variables: {
          customConfig: JSON.stringify(changedValues)
        }
      });

      console.log('[Settings] Mutation response:', response);

      setSuccess(true);
      setSaving(false);

      // Reload configuration
      setTimeout(() => {
        console.log('[Settings] Reloading configuration...');
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

  const renderField = (key, property) => {
    if (!property) return null;

    const value = formValues[key];
    const isCustomized = Object.prototype.hasOwnProperty.call(customConfig, key);
    const validationError = validationErrors[key];

    // Note: chat_deployed check removed - chat is always deployed with SAM stack
    // All chat fields are now always visible

    // Log when rendering chat_allow_document_access
    if (key === 'chat_allow_document_access') {
      console.log(`[Settings] Rendering chat_allow_document_access toggle:`, {
        value,
        isCustomized,
        formValues_value: formValues[key],
        customConfig_value: customConfig[key],
        defaultConfig_value: defaultConfig[key]
      });
    }

    // Special handling for chat_cdn_url - display with embed code
    if (key === 'chat_cdn_url' && value) {
      return (
        <Alert type="success" header="Web Component Embed Code">
          <SpaceBetween size="s">
            <Box variant="p">
              Copy and paste this code into any HTML page to add the chat component:
            </Box>
            <Box>
              <code style={{ display: 'block', whiteSpace: 'pre-wrap', padding: '12px', background: '#f4f4f4', borderRadius: '4px' }}>
                {`<script src="${value}"></script>\n<ragstack-chat conversation-id="my-site"></ragstack-chat>`}
              </code>
            </Box>
            <CopyToClipboard
              copyText={`<script src="${value}"></script>\n<ragstack-chat conversation-id="my-site"></ragstack-chat>`}
              copyButtonText="Copy Embed Code"
              copySuccessText="Copied!"
            />
            <Box variant="small" color="text-body-secondary">
              CDN URL: {value}
            </Box>
          </SpaceBetween>
        </Alert>
      );
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
            selectedOption={{ label: value || '', value: value || '' }}
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
              console.log(`[Settings] Toggle changed for ${key}:`, {
                oldValue: value,
                newValue: detail.checked,
                field: key
              });
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
      return renderObjectField(key, property, value || {});
    }

    return null;
  };

  const renderObjectField = (parentKey, property, value) => {
    const isCustomized = Object.prototype.hasOwnProperty.call(customConfig, parentKey);

    const handleNestedChange = (nestedKey, nestedValue) => {
      const updatedObject = { ...value, [nestedKey]: nestedValue };
      setFormValues({ ...formValues, [parentKey]: updatedObject });

      // Validate theme overrides
      if (parentKey === 'chat_theme_overrides') {
        const validation = validateThemeOverrides(updatedObject);
        if (!validation.valid) {
          setValidationErrors({ ...validationErrors, [parentKey]: validation.errors.join('; ') });
        } else {
          const newErrors = { ...validationErrors };
          delete newErrors[parentKey];
          setValidationErrors(newErrors);
        }
      }
    };

    return (
      <ExpandableSection
        headerText={property.description || parentKey}
        variant="container"
        defaultExpanded={isCustomized}
      >
        <SpaceBetween size="s">
          {isCustomized && (
            <Alert type="info" dismissible={false}>
              Customized from default
            </Alert>
          )}

          {validationErrors[parentKey] && (
            <Alert type="error">
              {validationErrors[parentKey]}
            </Alert>
          )}

          {Object.entries(property.properties).map(([nestedKey, nestedProp]) => {
            const nestedValue = value[nestedKey] || '';

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
        </SpaceBetween>
      </ExpandableSection>
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

      <Container header={<Header variant="h2">Runtime Configuration</Header>}>
        <Form
          actions={
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={handleReset} disabled={saving}>
                Reset
              </Button>
              <Button variant="primary" onClick={handleSave} loading={saving}>
                Save changes
              </Button>
            </SpaceBetween>
          }
        >
          <SpaceBetween size="l">
            {schema.properties &&
              Object.entries(schema.properties)
                .sort((a, b) => (a[1].order || 999) - (b[1].order || 999))
                .map(([key, property]) => (
                  <React.Fragment key={key}>
                    {renderField(key, property)}
                  </React.Fragment>
                ))}
          </SpaceBetween>
        </Form>
      </Container>
    </SpaceBetween>
  );
}
