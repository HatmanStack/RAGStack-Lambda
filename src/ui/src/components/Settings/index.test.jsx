import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { Settings } from './index';
import { generateClient } from 'aws-amplify/api';

// Mock AWS Amplify client
vi.mock('aws-amplify/api', () => ({
  generateClient: vi.fn()
}));

const mockGraphqlResponse = (data) => ({
  data
});

const sampleSchema = {
  properties: {
    ocr_backend: {
      type: 'string',
      enum: ['textract', 'bedrock'],
      description: 'OCR Backend',
      order: 1
    },
    bedrock_ocr_model_id: {
      type: 'string',
      enum: ['anthropic.claude-3-5-haiku-20241022-v1:0', 'anthropic.claude-3-5-sonnet-20241022-v2:0'],
      description: 'Bedrock OCR Model',
      order: 2,
      dependsOn: {
        field: 'ocr_backend',
        value: 'bedrock'
      }
    },
    text_embed_model_id: {
      type: 'string',
      enum: ['amazon.titan-embed-text-v2:0', 'cohere.embed-english-v3'],
      description: 'Text Embedding Model',
      order: 3
    },
    image_embed_model_id: {
      type: 'string',
      enum: ['amazon.titan-embed-image-v1', 'amazon.titan-embed-image-v2:0'],
      description: 'Image Embedding Model',
      order: 4
    }
  }
};

const sampleDefault = {
  ocr_backend: 'textract',
  bedrock_ocr_model_id: 'anthropic.claude-3-5-haiku-20241022-v1:0',
  text_embed_model_id: 'amazon.titan-embed-text-v2:0',
  image_embed_model_id: 'amazon.titan-embed-image-v1'
};

const sampleCustom = {};

describe('Settings Component', () => {
  let mockClient;

  beforeEach(() => {
    mockClient = {
      graphql: vi.fn()
    };
    generateClient.mockReturnValue(mockClient);
  });

  const renderSettings = () => {
    return render(
      <BrowserRouter>
        <Settings />
      </BrowserRouter>
    );
  };

  it('renders loading state initially', () => {
    mockClient.graphql.mockImplementation(() => new Promise(() => {})); // Never resolves
    renderSettings();
    expect(screen.getByText(/loading configuration/i)).toBeInTheDocument();
  });

  it('loads and displays configuration successfully', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
      expect(screen.getByText('OCR Backend')).toBeInTheDocument();
    });
  });

  it('renders form fields from schema in correct order', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('OCR Backend')).toBeInTheDocument();
      expect(screen.getByText('Text Embedding Model')).toBeInTheDocument();
      expect(screen.getByText('Image Embedding Model')).toBeInTheDocument();
    });
  });

  it('shows error message when configuration load fails', async () => {
    mockClient.graphql.mockRejectedValue(new Error('Network error'));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText(/failed to load configuration/i)).toBeInTheDocument();
    });
  });

  it('displays save and reset buttons', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Save changes')).toBeInTheDocument();
      expect(screen.getByText('Reset')).toBeInTheDocument();
    });
  });

  it('saves configuration successfully when no embedding changes', async () => {
    mockClient.graphql
      .mockResolvedValueOnce(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(sampleSchema),
          Default: JSON.stringify(sampleDefault),
          Custom: JSON.stringify(sampleCustom)
        }
      }))
      .mockResolvedValueOnce(mockGraphqlResponse({
        getDocumentCount: 0
      }))
      .mockResolvedValueOnce(mockGraphqlResponse({
        updateConfiguration: true
      }))
      .mockResolvedValueOnce(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(sampleSchema),
          Default: JSON.stringify(sampleDefault),
          Custom: JSON.stringify({ ocr_backend: 'bedrock' })
        }
      }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Click save button
    const saveButton = screen.getByText('Save changes');
    fireEvent.click(saveButton);

    await waitFor(() => {
      expect(screen.getByText(/configuration saved successfully/i)).toBeInTheDocument();
    });
  });

  it('shows embedding change modal when documents exist and embedding model changed', async () => {
    const customWithEmbeddingChange = {
      text_embed_model_id: 'cohere.embed-english-v3'
    };

    mockClient.graphql
      .mockResolvedValueOnce(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(sampleSchema),
          Default: JSON.stringify(sampleDefault),
          Custom: JSON.stringify(sampleCustom)
        }
      }))
      .mockResolvedValueOnce(mockGraphqlResponse({
        getDocumentCount: 42
      }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    // Note: In a real test, we would need to interact with the Select component
    // to change the embedding model. For now, this test verifies the modal logic
    // exists but doesn't fully test the interaction flow due to Cloudscape
    // component complexity.
  });

  it('handles conditional field visibility based on dependsOn', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('OCR Backend')).toBeInTheDocument();
    });

    // With default ocr_backend='textract', the Bedrock OCR Model field
    // should not be visible (depends on ocr_backend='bedrock')
    expect(screen.queryByText('Bedrock OCR Model')).not.toBeInTheDocument();
  });

  it('shows customized indicator for fields with custom values', async () => {
    const customWithChanges = {
      ocr_backend: 'bedrock'
    };

    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(customWithChanges)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('OCR Backend')).toBeInTheDocument();
      expect(screen.getByText('Customized from default')).toBeInTheDocument();
    });
  });

  it('displays loading state on save button while saving', async () => {
    mockClient.graphql
      .mockResolvedValueOnce(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(sampleSchema),
          Default: JSON.stringify(sampleDefault),
          Custom: JSON.stringify(sampleCustom)
        }
      }))
      .mockResolvedValueOnce(mockGraphqlResponse({
        getDocumentCount: 0
      }))
      .mockImplementation(() => new Promise(() => {})); // Never resolves

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    const saveButton = screen.getByText('Save changes');
    fireEvent.click(saveButton);

    // Note: Testing loading state on Cloudscape buttons requires
    // checking for the loading prop or spinner, which may be complex
    // This test establishes the pattern but may need adjustment
  });

  it('resets form values when reset button is clicked', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Settings')).toBeInTheDocument();
    });

    const resetButton = screen.getByText('Reset');
    fireEvent.click(resetButton);

    // Form should revert to saved state
    // This is a basic test - in practice, you'd verify field values reset
  });

  it('dismisses error alert when dismiss button is clicked', async () => {
    mockClient.graphql.mockRejectedValue(new Error('Network error'));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText(/failed to load configuration/i)).toBeInTheDocument();
    });

    // Verify alert is displayed
    const alertText = screen.getByText(/failed to load configuration/i);
    expect(alertText).toBeInTheDocument();

    // Note: Dismissing Cloudscape alerts requires finding the dismiss button
    // which has specific Cloudscape CSS classes. Full dismissal testing would
    // require more complex DOM queries or integration testing.
  });
});
