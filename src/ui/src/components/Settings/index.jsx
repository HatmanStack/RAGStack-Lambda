import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Container,
  Header,
  SpaceBetween,
  Form,
  FormField,
  Select,
  Button,
  Alert,
  Modal,
  Box,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import { getDocumentCount } from '../../graphql/queries/getDocumentCount';

export function Settings() {
  const navigate = useNavigate();
  const client = generateClient();

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

  // State for embedding change detection
  const [showEmbeddingModal, setShowEmbeddingModal] = useState(false);
  const [pendingEmbeddingChanges, setPendingEmbeddingChanges] = useState(null);
  const [documentCount, setDocumentCount] = useState(0);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
  }, []);

  const loadConfiguration = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await client.graphql({ query: getConfiguration });
      const config = response.data.getConfiguration;

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
  };

  const checkDocumentCount = async () => {
    try {
      const response = await client.graphql({ query: getDocumentCount });
      const count = response.data.getDocumentCount;
      setDocumentCount(count);
      return count;
    } catch (err) {
      console.error('Error checking document count:', err);
      return 0;
    }
  };

  const handleSave = async () => {
    try {
      // Get previous effective configuration (Custom overrides Default)
      const previousEffective = { ...defaultConfig, ...customConfig };

      // Check if embedding models changed from previous effective values
      const embeddingFieldsChanged =
        formValues.text_embed_model_id !== previousEffective.text_embed_model_id ||
        formValues.image_embed_model_id !== previousEffective.image_embed_model_id;

      if (embeddingFieldsChanged) {
        // Check if documents exist
        const count = await checkDocumentCount();

        if (count > 0) {
          // Show modal for user decision
          setPendingEmbeddingChanges(formValues);
          setShowEmbeddingModal(true);
          return; // Don't save yet
        }
      }

      // No embedding changes or no documents, save directly
      await saveConfiguration(formValues);

    } catch (err) {
      console.error('Error in handleSave:', err);
      setError('Failed to save configuration. Please try again.');
    }
  };

  const saveConfiguration = async (values) => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(false);

      // Only save values that differ from defaults
      const changedValues = {};
      Object.keys(values).forEach(key => {
        if (values[key] !== defaultConfig[key]) {
          changedValues[key] = values[key];
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
      console.error('Error saving configuration:', err);
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

  const handleEmbeddingModalChoice = async (choice) => {
    setShowEmbeddingModal(false);

    if (choice === 'cancel') {
      // Revert embedding field changes
      setPendingEmbeddingChanges(null);
      return;
    }

    if (choice === 'continue') {
      // Save with mixed embeddings
      await saveConfiguration(pendingEmbeddingChanges);
      setPendingEmbeddingChanges(null);
    }

    if (choice === 're-embed') {
      // Save config and trigger re-embedding job
      await saveConfiguration(pendingEmbeddingChanges);
      setPendingEmbeddingChanges(null);

      // TODO: Trigger re-embedding job (Phase 5)
      alert('Re-embedding job will be implemented in Phase 5');
    }
  };

  const renderField = (key, property) => {
    if (!property) return null;

    const value = formValues[key] || '';
    const isCustomized = customConfig.hasOwnProperty(key);

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
          key={key}
          label={property.description || key}
          description={isCustomized ? 'Customized from default' : ''}
        >
          <Select
            selectedOption={{ label: value, value }}
            onChange={({ detail }) => {
              setFormValues({ ...formValues, [key]: detail.selectedOption.value });
            }}
            options={property.enum.map(v => ({ label: v, value: v }))}
          />
        </FormField>
      );
    }

    return null;
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
                .map(([key, property]) => renderField(key, property))}
          </SpaceBetween>
        </Form>
      </Container>

      {/* Embedding Change Modal */}
      <Modal
        visible={showEmbeddingModal}
        onDismiss={() => handleEmbeddingModalChoice('cancel')}
        header="Embedding Model Change Detected"
        footer={
          <Box float="right">
            <SpaceBetween direction="horizontal" size="xs">
              <Button variant="link" onClick={() => handleEmbeddingModalChoice('cancel')}>
                Cancel
              </Button>
              <Button variant="normal" onClick={() => handleEmbeddingModalChoice('continue')}>
                Continue with mixed embeddings
              </Button>
              <Button variant="primary" onClick={() => handleEmbeddingModalChoice('re-embed')}>
                Re-embed all documents
              </Button>
            </SpaceBetween>
          </Box>
        }
      >
        <SpaceBetween size="m">
          <Box>
            You have changed the embedding model, and you have <strong>{documentCount} documents</strong> already processed with the previous model.
          </Box>
          <Box>
            <strong>Options:</strong>
          </Box>
          <Box>
            <ul>
              <li>
                <strong>Continue with mixed embeddings:</strong> New documents will use the new model.
                Existing documents keep their current embeddings. Search quality may be inconsistent.
              </li>
              <li>
                <strong>Re-embed all documents:</strong> Regenerate embeddings for all documents using
                the new model. This ensures consistency but takes time (estimated: {Math.ceil(documentCount / 10)} minutes).
              </li>
              <li>
                <strong>Cancel:</strong> Don't change the embedding model.
              </li>
            </ul>
          </Box>
        </SpaceBetween>
      </Modal>
    </SpaceBetween>
  );
}
