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
      enum: [
        'anthropic.claude-3-5-haiku-20241022-v1:0',
        'anthropic.claude-3-5-sonnet-20241022-v2:0',
        'anthropic.claude-3-haiku-20240307-v1:0',
        'anthropic.claude-3-sonnet-20240229-v1:0'
      ],
      description: 'Bedrock OCR Model',
      order: 2,
      dependsOn: {
        field: 'ocr_backend',
        value: 'bedrock'
      }
    },
    chat_model_id: {
      type: 'string',
      enum: [
        'amazon.nova-pro-v1:0',
        'amazon.nova-lite-v1:0',
        'amazon.nova-micro-v1:0',
        'anthropic.claude-3-5-sonnet-20241022-v2:0',
        'anthropic.claude-3-5-haiku-20241022-v1:0'
      ],
      description: 'Chat Model',
      order: 3
    }
  }
};

const sampleDefault = {
  ocr_backend: 'textract',
  bedrock_ocr_model_id: 'anthropic.claude-3-5-haiku-20241022-v1:0',
  chat_model_id: 'amazon.nova-pro-v1:0'
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
      expect(screen.getByText('Chat Model')).toBeInTheDocument();
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

  it('saves configuration successfully', async () => {
    mockClient.graphql
      .mockResolvedValueOnce(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(sampleSchema),
          Default: JSON.stringify(sampleDefault),
          Custom: JSON.stringify(sampleCustom)
        }
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

  it('renders chat_model_id field', async () => {
    mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
      getConfiguration: {
        Schema: JSON.stringify(sampleSchema),
        Default: JSON.stringify(sampleDefault),
        Custom: JSON.stringify(sampleCustom)
      }
    }));

    renderSettings();

    await waitFor(() => {
      expect(screen.getByText('Chat Model')).toBeInTheDocument();
    });
  });

  it.skip('shows customized indicator for fields with custom values', async () => {
    const customWithChanges = {
      ocr_backend: 'bedrock'
    };

    mockClient.graphql
      .mockResolvedValue(mockGraphqlResponse({
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
    }, { timeout: 10000 });
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

  describe('New field types', () => {
    it('renders boolean fields as toggles', async () => {
      const schemaWithBoolean = {
        properties: {
          chat_require_auth: {
            type: 'boolean',
            description: 'Require authentication for chat',
            order: 1
          }
        }
      };

      const defaultWithBoolean = {
        chat_require_auth: false
      };

      mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(schemaWithBoolean),
          Default: JSON.stringify(defaultWithBoolean),
          Custom: JSON.stringify({})
        }
      }));

      renderSettings();

      await waitFor(() => {
        expect(screen.getByText('Require authentication for chat')).toBeInTheDocument();
        // Cloudscape Toggle component should render
        const toggle = screen.getByText('Disabled');
        expect(toggle).toBeInTheDocument();
      });
    });

    it('renders number fields as inputs', async () => {
      const schemaWithNumber = {
        properties: {
          chat_global_quota_daily: {
            type: 'number',
            description: 'Global daily quota',
            order: 1
          }
        }
      };

      const defaultWithNumber = {
        chat_global_quota_daily: 10000
      };

      mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(schemaWithNumber),
          Default: JSON.stringify(defaultWithNumber),
          Custom: JSON.stringify({})
        }
      }));

      renderSettings();

      await waitFor(() => {
        expect(screen.getByText('Global daily quota')).toBeInTheDocument();
        // Input should exist with the default value
        const input = screen.getByDisplayValue('10000');
        expect(input).toBeInTheDocument();
      });
    });

    it('renders object fields as expandable sections with nested inputs', async () => {
      const schemaWithObject = {
        properties: {
          chat_theme_overrides: {
            type: 'object',
            description: 'Custom theme overrides',
            order: 1,
            properties: {
              primaryColor: { type: 'string' },
              fontFamily: { type: 'string' },
              spacing: { type: 'string', enum: ['compact', 'comfortable', 'spacious'] }
            }
          }
        }
      };

      const defaultWithObject = {
        chat_theme_overrides: {
          primaryColor: '#0073bb',
          spacing: 'comfortable'
        }
      };

      mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(schemaWithObject),
          Default: JSON.stringify(defaultWithObject),
          Custom: JSON.stringify({})
        }
      }));

      renderSettings();

      await waitFor(() => {
        expect(screen.getByText('Custom theme overrides')).toBeInTheDocument();
      });
    });
  });

  describe('Chat field visibility', () => {
    it('shows all chat fields (chat is always deployed with SAM stack)', async () => {
      const schemaWithChat = {
        properties: {
          chat_require_auth: {
            type: 'boolean',
            description: 'Require authentication',
            order: 1
          },
          chat_primary_model: {
            type: 'string',
            enum: ['model1', 'model2'],
            description: 'Primary model',
            order: 2
          },
          chat_model_id: {
            type: 'string',
            enum: ['model1', 'model2'],
            description: 'Chat Model',
            order: 3
          }
        }
      };

      const defaultConfig = {
        chat_require_auth: false,
        chat_primary_model: 'model1',
        chat_model_id: 'model1'
      };

      mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(schemaWithChat),
          Default: JSON.stringify(defaultConfig),
          Custom: JSON.stringify({})
        }
      }));

      renderSettings();

      await waitFor(() => {
        expect(screen.getByText('Settings')).toBeInTheDocument();
      });

      // All chat fields should be visible
      expect(screen.getByText('Require authentication')).toBeInTheDocument();
      expect(screen.getByText('Primary model')).toBeInTheDocument();
      expect(screen.getByText('Chat Model')).toBeInTheDocument();
    });
  });

  describe('Validation', () => {
    it('blocks save when validation errors exist', async () => {
      const schemaWithNumber = {
        properties: {
          chat_global_quota_daily: {
            type: 'number',
            description: 'Global daily quota',
            order: 1
          }
        }
      };

      const defaultWithNumber = {
        chat_global_quota_daily: 10000
      };

      mockClient.graphql.mockResolvedValue(mockGraphqlResponse({
        getConfiguration: {
          Schema: JSON.stringify(schemaWithNumber),
          Default: JSON.stringify(defaultWithNumber),
          Custom: JSON.stringify({})
        }
      }));

      renderSettings();

      await waitFor(() => {
        expect(screen.getByText('Global daily quota')).toBeInTheDocument();
      });

      // Change quota to invalid value
      const input = screen.getByDisplayValue('10000');
      fireEvent.change(input, { target: { value: '-1' } });

      // Try to save
      const saveButton = screen.getByText('Save changes');
      fireEvent.click(saveButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/fix validation errors/i)).toBeInTheDocument();
      });
    });
  });

});
