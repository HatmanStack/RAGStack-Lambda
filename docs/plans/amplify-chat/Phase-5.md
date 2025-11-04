# Phase 5: SAM UI Configuration Interface

**Goal:** Add chat configuration UI to SAM admin interface for runtime settings management.

**Dependencies:** Phase 0 (ADRs), Phase 1 (ConfigurationTable schema), Phase 4 (runtime logic reading config)

**Deliverables:**
- ChatSettings React component
- Integration into existing Settings page
- GraphQL resolver for updating chat config
- Conditional rendering based on `chat_deployed` flag
- Unit tests for UI components

**Estimated Scope:** ~20,000 tokens

---

## Context

This phase adds the admin UI for managing chat configuration. After this phase:

- Admins can change chat settings from web UI (no DynamoDB console needed)
- Settings page shows chat section only if Amplify deployed
- Changes take effect within 60 seconds (config cache TTL)
- Admins can copy embed code directly from UI

**Key Files:**
- `src/ui/src/components/ChatSettings.tsx` (new)
- `src/ui/src/pages/Settings.tsx` (modify)
- `src/lambda/configuration_resolver/` (modify or create)

---

## Task 1: Create ChatSettings Component

### Goal

Create `ChatSettings.tsx` component that renders chat configuration form.

### Files to Create

- `src/ui/src/components/ChatSettings.tsx`

### Background

The existing Settings page likely has an `OcrSettings` component (or similar). We'll follow the same pattern for ChatSettings.

### Instructions

Create `src/ui/src/components/ChatSettings.tsx`:

```tsx
/**
 * ChatSettings Component
 *
 * Configuration interface for Amplify Chat component settings.
 * Allows admins to control authentication, models, quotas, and themes.
 */

import React from 'react';
import {
  Container,
  Header,
  FormField,
  Toggle,
  Select,
  Input,
  Tiles,
  ExpandableSection,
  SpaceBetween,
  Box,
  Alert,
  Button,
  CodeEditor,
  ColumnLayout,
} from '@cloudscape-design/components';

interface ChatSettingsProps {
  /** Current configuration */
  config: any;
  /** CDN URL for embed code display */
  cdnUrl?: string;
  /** Callback when config changes */
  onUpdate: (field: string, value: any) => void;
}

export function ChatSettings({ config, cdnUrl, onUpdate }: ChatSettingsProps) {
  const [embedCodeCopied, setEmbedCodeCopied] = React.useState(false);

  // Generate embed code
  const embedCode = cdnUrl
    ? `<script src="${cdnUrl}"></script>\n<amplify-chat conversation-id="my-site"></amplify-chat>`
    : 'Deploying...';

  const copyEmbedCode = () => {
    navigator.clipboard.writeText(embedCode);
    setEmbedCodeCopied(true);
    setTimeout(() => setEmbedCodeCopied(false), 2000);
  };

  return (
    <Container header={<Header variant="h2">Chat Component Settings</Header>}>
      <SpaceBetween size="l">
        {/* Authentication */}
        <FormField
          label="Require Authentication"
          description="When enabled, users must provide authentication tokens to use chat."
        >
          <Toggle
            checked={config.chat_require_auth || false}
            onChange={({ detail }) => onUpdate('chat_require_auth', detail.checked)}
          >
            {config.chat_require_auth
              ? 'Authentication required (users must pass tokens)'
              : 'Public access (anonymous chat enabled)'}
          </Toggle>
        </FormField>

        {/* Model Selection */}
        <Header variant="h3">Model Configuration</Header>

        <ColumnLayout columns={2}>
          <FormField
            label="Primary Model"
            description="Used until quotas are reached. Higher quality, higher cost."
          >
            <Select
              selectedOption={{
                value: config.chat_primary_model || 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
              }}
              onChange={({ detail }) => onUpdate('chat_primary_model', detail.selectedOption.value)}
              options={[
                {
                  value: 'us.anthropic.claude-sonnet-4-20250514-v1:0',
                  label: 'Claude Sonnet 4 (High quality, higher cost)',
                },
                {
                  value: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                  label: 'Claude Haiku 4.5 (Balanced)',
                },
                {
                  value: 'us.amazon.nova-pro-v1:0',
                  label: 'Amazon Nova Pro (Fast, balanced)',
                },
                {
                  value: 'us.amazon.nova-lite-v1:0',
                  label: 'Amazon Nova Lite (Economical)',
                },
              ]}
            />
          </FormField>

          <FormField
            label="Fallback Model"
            description="Automatically used after quotas exceeded. Lower cost."
          >
            <Select
              selectedOption={{
                value: config.chat_fallback_model || 'us.amazon.nova-micro-v1:0',
              }}
              onChange={({ detail }) => onUpdate('chat_fallback_model', detail.selectedOption.value)}
              options={[
                {
                  value: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
                  label: 'Claude Haiku 4.5',
                },
                {
                  value: 'us.amazon.nova-micro-v1:0',
                  label: 'Amazon Nova Micro (Most economical)',
                },
                {
                  value: 'us.amazon.nova-lite-v1:0',
                  label: 'Amazon Nova Lite',
                },
              ]}
            />
          </FormField>
        </ColumnLayout>

        {/* Rate Limits */}
        <Header variant="h3">Rate Limits (Cost Protection)</Header>

        <ColumnLayout columns={2}>
          <FormField
            label="Global Daily Quota"
            description="Total messages per day across all users on primary model. After this, everyone gets fallback model."
          >
            <Input
              type="number"
              value={String(config.chat_global_quota_daily || 10000)}
              onChange={({ detail }) => onUpdate('chat_global_quota_daily', parseInt(detail.value) || 0)}
            />
          </FormField>

          <FormField
            label="Per-User Daily Quota"
            description="Max messages per user per day on primary model. Protects against individual abuse."
          >
            <Input
              type="number"
              value={String(config.chat_per_user_quota_daily || 100)}
              onChange={({ detail }) => onUpdate('chat_per_user_quota_daily', parseInt(detail.value) || 0)}
            />
          </FormField>
        </ColumnLayout>

        <Alert type="info">
          When quotas are exceeded, chat automatically switches to the fallback model.
          Users still get responses, just with a more economical model. This prevents unexpected bills.
        </Alert>

        {/* Theme */}
        <Header variant="h3">Theme</Header>

        <FormField label="Theme Preset">
          <Tiles
            columns={3}
            items={[
              { value: 'light', label: 'Light', description: 'Clean, bright interface' },
              { value: 'dark', label: 'Dark', description: 'Dark mode for low-light' },
              { value: 'brand', label: 'Brand', description: 'Match your brand colors' },
            ]}
            value={config.chat_theme_preset || 'light'}
            onChange={({ detail }) => onUpdate('chat_theme_preset', detail.value)}
          />
        </FormField>

        <ExpandableSection headerText="Custom Theme Overrides (Optional)">
          <SpaceBetween size="s">
            <FormField
              label="Primary Color"
              description="Hex color code for buttons and accents"
            >
              <Input
                type="text"
                value={config.chat_theme_overrides?.primaryColor || ''}
                onChange={({ detail }) =>
                  onUpdate('chat_theme_overrides', {
                    ...config.chat_theme_overrides,
                    primaryColor: detail.value,
                  })
                }
                placeholder="#0073bb"
              />
            </FormField>

            <FormField
              label="Font Family"
              description="CSS font family string"
            >
              <Input
                type="text"
                value={config.chat_theme_overrides?.fontFamily || ''}
                onChange={({ detail }) =>
                  onUpdate('chat_theme_overrides', {
                    ...config.chat_theme_overrides,
                    fontFamily: detail.value,
                  })
                }
                placeholder="Inter, system-ui, sans-serif"
              />
            </FormField>

            <FormField label="Spacing">
              <Select
                selectedOption={{
                  value: config.chat_theme_overrides?.spacing || 'comfortable',
                }}
                onChange={({ detail }) =>
                  onUpdate('chat_theme_overrides', {
                    ...config.chat_theme_overrides,
                    spacing: detail.selectedOption.value,
                  })
                }
                options={[
                  { value: 'compact', label: 'Compact' },
                  { value: 'comfortable', label: 'Comfortable' },
                  { value: 'spacious', label: 'Spacious' },
                ]}
              />
            </FormField>
          </SpaceBetween>
        </ExpandableSection>

        {/* Embed Code */}
        {cdnUrl && (
          <Alert type="success">
            <Box variant="h4">Embed on Your Website</Box>
            <Box variant="p" padding={{ top: 's' }}>
              Copy and paste this code into any HTML page to add the chat component:
            </Box>
            <Box padding={{ top: 's' }}>
              <CodeEditor
                ace={window.ace}
                language="html"
                value={embedCode}
                preferences={{
                  wrapLines: true,
                  showGutter: false,
                }}
                editorContentHeight={80}
                readOnly
              />
            </Box>
            <Box padding={{ top: 's' }}>
              <Button
                iconName="copy"
                onClick={copyEmbedCode}
              >
                {embedCodeCopied ? 'Copied!' : 'Copy Embed Code'}
              </Button>
            </Box>
          </Alert>
        )}
      </SpaceBetween>
    </Container>
  );
}
```

### Verification Checklist

- [ ] Component accepts config, cdnUrl, onUpdate props
- [ ] Renders authentication toggle
- [ ] Renders model selection (primary + fallback)
- [ ] Renders quota inputs (global + per-user)
- [ ] Renders theme presets and overrides
- [ ] Displays embed code if cdnUrl provided
- [ ] Copy button works
- [ ] Uses Cloudscape Design components
- [ ] No TypeScript errors: `npx tsc --noEmit` in src/ui

### Commit

```bash
git add src/ui/src/components/ChatSettings.tsx
git commit -m "feat(ui): create ChatSettings component for chat configuration

- Add authentication toggle
- Add primary and fallback model selectors
- Add quota inputs for cost protection
- Add theme presets and custom overrides
- Display embed code with copy button
- Use Cloudscape Design System components"
```

---

## Task 2: Integrate ChatSettings into Settings Page

### Goal

Modify existing Settings page to conditionally render ChatSettings component.

### Files to Modify

- `src/ui/src/pages/Settings.tsx` (or wherever main settings page is)

### Background

The Settings page likely has a structure like:
```tsx
export function Settings() {
  return (
    <SpaceBetween>
      <OcrSettings ... />
      {/* Chat settings will go here */}
    </SpaceBetween>
  );
}
```

We need to:
1. Check if `chat_deployed` is true
2. If yes, render ChatSettings component
3. Pass config, cdnUrl, and update handler

### Instructions

1. **Import ChatSettings:**

   ```tsx
   import { ChatSettings } from '../components/ChatSettings';
   ```

2. **Add state for CDN URL:**

   ```tsx
   const [cdnUrl, setCdnUrl] = useState<string | null>(null);
   ```

3. **Fetch CDN URL when component mounts (if chat deployed):**

   ```tsx
   useEffect(() => {
     if (config?.chat_deployed) {
       // Fetch CDN URL from Amplify stack outputs
       // This could be from GraphQL query or environment variable
       // For now, we'll assume it's in config or fetched separately

       // Example: Call API to get Amplify outputs
       fetch('/api/amplify/outputs')
         .then(res => res.json())
         .then(data => setCdnUrl(data.WebComponentCDN))
         .catch(err => console.error('Failed to fetch CDN URL:', err));
    }
   }, [config?.chat_deployed]);
   ```

4. **Render ChatSettings conditionally:**

   ```tsx
   export function Settings() {
     const [config, setConfig] = useState<any>(null);
     const [cdnUrl, setCdnUrl] = useState<string | null>(null);

     // ... existing config fetch logic ...

     const handleConfigUpdate = (field: string, value: any) => {
       setConfig({ ...config, [field]: value });
     };

     const handleSave = async () => {
       // Save config to backend (Task 3 will implement the API)
       await saveConfiguration(config);
     };

     return (
       <Container>
         <Header variant="h1">Configuration</Header>

         <SpaceBetween size="l">
           {/* Existing OCR/document settings */}
           <OcrSettings config={config} onUpdate={handleConfigUpdate} />

           {/* NEW: Conditionally render chat settings */}
           {config?.chat_deployed && (
             <ChatSettings
               config={config}
               cdnUrl={cdnUrl}
               onUpdate={handleConfigUpdate}
             />
           )}

           <Button variant="primary" onClick={handleSave}>
             Save Configuration
           </Button>
         </SpaceBetween>
       </Container>
     );
   }
   ```

5. **Handle CDN URL retrieval:**

   **Option A (Recommended): Pass via environment variable during UI build**

   In `publish.py`, after retrieving Amplify outputs, write to UI env file:

   ```python
   # In configure_ui() or similar function
   if chat_deployed:
       amplify_outputs = get_amplify_stack_outputs(project_name, region)
       cdn_url = amplify_outputs.get('WebComponentCDN', '')

       # Append to .env.production
       env_file = Path("src/ui/.env.production")
       existing_content = env_file.read_text() if env_file.exists() else ''
       env_file.write_text(existing_content + f'\nREACT_APP_CHAT_CDN_URL={cdn_url}\n')
   ```

   Then in React:
   ```tsx
   useEffect(() => {
     if (config?.chat_deployed) {
       const url = process.env.REACT_APP_CHAT_CDN_URL || null;
       setCdnUrl(url);
     }
   }, [config?.chat_deployed]);
   ```

   **Option B: Store in ConfigurationTable**

   Add `chat_cdn_url` field to ConfigurationTable during deployment:
   ```python
   # In amplify_deploy(), after getting cdn_url:
   dynamodb = boto3.resource('dynamodb', region_name=region)
   table = dynamodb.Table(config_table_name)
   table.update_item(
       Key={'Configuration': 'Default'},
       UpdateExpression='SET chat_cdn_url = :url',
       ExpressionAttributeValues={':url': cdn_url}
   )
   ```

   Then fetch via GraphQL in Settings page alongside other config.

   **Implementation Choice:** Use Option A (environment variable) for simplicity. CDN URL rarely changes after deployment.

### Verification Checklist

- [ ] ChatSettings imported
- [ ] Conditional rendering based on `config.chat_deployed`
- [ ] CDN URL passed to ChatSettings (even if placeholder)
- [ ] Config update handler wired to ChatSettings
- [ ] Save button triggers config save
- [ ] No TypeScript errors

### Commit

```bash
git add src/ui/src/pages/Settings.tsx
git commit -m "feat(ui): integrate ChatSettings into Settings page

- Import and conditionally render ChatSettings component
- Check chat_deployed flag before displaying
- Pass config, cdnUrl, and update handler to ChatSettings
- Wire up save button to persist changes
- Fetch CDN URL from environment or API"
```

---

## Task 3: Create Configuration Update API

### Goal

Add GraphQL mutation or Lambda resolver to update ConfigurationTable.

### Files to Modify/Create

**Option A:** If using AppSync GraphQL already:
- Modify `src/lambda/configuration_resolver/` (or create it)
- Add mutation to GraphQL schema

**Option B:** If using REST API:
- Create new Lambda in `src/lambda/update_configuration/`
- Add API Gateway route

**We'll assume Option A (GraphQL) to match existing patterns.**

### Instructions

1. **Check if `configuration_resolver` Lambda exists:**

   ```bash
   ls src/lambda/ | grep configuration
   ```

   If it doesn't exist, create it:

   ```bash
   mkdir -p src/lambda/configuration_resolver
   ```

2. **Create or modify resolver Lambda:**

   Create `src/lambda/configuration_resolver/app.py`:

   ```python
   """
   Configuration Resolver for GraphQL mutations.

   Handles updating ConfigurationTable from admin UI.
   """

   import json
   import os
   import boto3
   from botocore.exceptions import ClientError

   dynamodb = boto3.resource('dynamodb')
   table_name = os.environ.get('CONFIGURATION_TABLE_NAME')

   def lambda_handler(event, context):
       """Handle GraphQL field resolver."""
       field = event.get('info', {}).get('fieldName')

       if field == 'updateChatConfig':
           return update_chat_config(event['arguments'])
       elif field == 'getChatConfig':
           return get_chat_config()
       else:
           raise ValueError(f"Unsupported field: {field}")

   def update_chat_config(args):
       """Update chat configuration in DynamoDB."""
       table = dynamodb.Table(table_name)

       # Build update expression
       update_expr = 'SET '
       expr_values = {}
       expr_names = {}

       # Map argument fields to DynamoDB attributes
       field_mapping = {
           'requireAuth': 'chat_require_auth',
           'primaryModel': 'chat_primary_model',
           'fallbackModel': 'chat_fallback_model',
           'globalQuotaDaily': 'chat_global_quota_daily',
           'perUserQuotaDaily': 'chat_per_user_quota_daily',
           'themePreset': 'chat_theme_preset',
           'themeOverrides': 'chat_theme_overrides',
       }

       for gql_field, db_field in field_mapping.items():
           if gql_field in args:
               update_expr += f'#{db_field} = :{db_field}, '
               expr_names[f'#{db_field}'] = db_field
               expr_values[f':{db_field}'] = args[gql_field]

       # Remove trailing comma
       update_expr = update_expr.rstrip(', ')

       try:
           table.update_item(
               Key={'Configuration': 'Default'},
               UpdateExpression=update_expr,
               ExpressionAttributeNames=expr_names,
               ExpressionAttributeValues=expr_values,
           )

           return {
               'success': True,
               'message': 'Configuration updated successfully',
           }

       except ClientError as e:
           print(f"Error updating config: {e}")
           return {
               'success': False,
               'message': f'Update failed: {str(e)}',
           }

   def get_chat_config():
       """Retrieve current chat configuration."""
       table = dynamodb.Table(table_name)

       try:
           response = table.get_item(Key={'Configuration': 'Default'})
           item = response.get('Item', {})

           return {
               'requireAuth': item.get('chat_require_auth', False),
               'primaryModel': item.get('chat_primary_model', ''),
               'fallbackModel': item.get('chat_fallback_model', ''),
               'globalQuotaDaily': item.get('chat_global_quota_daily', 10000),
               'perUserQuotaDaily': item.get('chat_per_user_quota_daily', 100),
               'themePreset': item.get('chat_theme_preset', 'light'),
               'themeOverrides': item.get('chat_theme_overrides', {}),
           }

       except ClientError as e:
           print(f"Error fetching config: {e}")
           raise ValueError(f'Failed to fetch configuration: {str(e)}')
   ```

3. **Add requirements.txt:**

   Create `src/lambda/configuration_resolver/requirements.txt`:

   ```
   boto3
   ```

4. **Update SAM template to include this Lambda:**

   In `template.yaml`, add a Lambda function resource:

   ```yaml
   ConfigurationResolverFunction:
     Type: AWS::Serverless::Function
     Properties:
       CodeUri: src/lambda/configuration_resolver/
       Handler: app.lambda_handler
       Runtime: python3.13
       Environment:
         Variables:
           CONFIGURATION_TABLE_NAME: !Ref ConfigurationTable
       Policies:
         - DynamoDBCrudPolicy:
             TableName: !Ref ConfigurationTable
   ```

   And add to GraphQL schema (if using AppSync):

   ```graphql
   type Mutation {
     updateChatConfig(
       requireAuth: Boolean
       primaryModel: String
       fallbackModel: String
       globalQuotaDaily: Int
       perUserQuotaDaily: Int
       themePreset: String
       themeOverrides: AWSJSON
     ): MutationResponse
   }

   type Query {
     getChatConfig: ChatConfig
   }

   type ChatConfig {
     requireAuth: Boolean
     primaryModel: String
     fallbackModel: String
     globalQuotaDaily: Int
     perUserQuotaDaily: Int
     themePreset: String
     themeOverrides: AWSJSON
   }

   type MutationResponse {
     success: Boolean!
     message: String
   }
   ```

### Verification Checklist

- [ ] Lambda function created in `src/lambda/configuration_resolver/`
- [ ] Handles `updateChatConfig` and `getChatConfig` operations
- [ ] Updates DynamoDB ConfigurationTable
- [ ] Returns success/failure response
- [ ] SAM template includes Lambda resource
- [ ] GraphQL schema has mutation and query definitions (if using AppSync)

### Testing

Create `src/lambda/configuration_resolver/test_app.py`:

```python
"""Tests for configuration resolver."""
import pytest
from unittest.mock import MagicMock, patch
from app import lambda_handler, update_chat_config, get_chat_config


def test_update_chat_config():
    """Test updating chat configuration."""
    with patch('app.dynamodb') as mock_db:
        mock_table = MagicMock()
        mock_db.Table.return_value = mock_table

        args = {
            'requireAuth': True,
            'primaryModel': 'claude-sonnet',
            'globalQuotaDaily': 5000,
        }

        result = update_chat_config(args)

        assert result['success'] is True
        assert mock_table.update_item.called


def test_get_chat_config():
    """Test retrieving chat configuration."""
    with patch('app.dynamodb') as mock_db:
        mock_table = MagicMock()
        mock_table.get_item.return_value = {
            'Item': {
                'chat_require_auth': False,
                'chat_primary_model': 'haiku',
            }
        }
        mock_db.Table.return_value = mock_table

        result = get_chat_config()

        assert result['requireAuth'] is False
        assert result['primaryModel'] == 'haiku'
```

Run: `pytest src/lambda/configuration_resolver/test_app.py`

### Commit

```bash
git add src/lambda/configuration_resolver/ template.yaml
git commit -m "feat(api): add configuration resolver Lambda for chat settings

- Create Lambda function to update ConfigurationTable
- Handle updateChatConfig mutation
- Handle getChatConfig query
- Add DynamoDB permissions in SAM template
- Include unit tests for resolver logic"
```

---

## Task 4: Wire Up UI to API

### Goal

Connect Settings page to configuration API (GraphQL or REST).

### Files to Modify

- `src/ui/src/pages/Settings.tsx`

### Instructions

1. **Add API client (assuming GraphQL):**

   ```tsx
   import { API, graphqlOperation } from 'aws-amplify';

   const updateChatConfigMutation = `
     mutation UpdateChatConfig(
       $requireAuth: Boolean
       $primaryModel: String
       $fallbackModel: String
       $globalQuotaDaily: Int
       $perUserQuotaDaily: Int
       $themePreset: String
       $themeOverrides: AWSJSON
     ) {
       updateChatConfig(
         requireAuth: $requireAuth
         primaryModel: $primaryModel
         fallbackModel: $fallbackModel
         globalQuotaDaily: $globalQuotaDaily
         perUserQuotaDaily: $perUserQuotaDaily
         themePreset: $themePreset
         themeOverrides: $themeOverrides
       ) {
         success
         message
       }
     }
   `;

   const getChatConfigQuery = `
     query GetChatConfig {
       getChatConfig {
         requireAuth
         primaryModel
         fallbackModel
         globalQuotaDaily
         perUserQuotaDaily
         themePreset
         themeOverrides
       }
     }
   `;
   ```

2. **Fetch config on mount:**

   ```tsx
   useEffect(() => {
     const fetchConfig = async () => {
       try {
         const result = await API.graphql(graphqlOperation(getChatConfigQuery));
         const chatConfig = result.data.getChatConfig;

         setConfig({
           ...config,
           ...chatConfig,
           chat_deployed: true, // Assume deployed if API returns config
         });
       } catch (error) {
         console.error('Failed to fetch config:', error);
       }
     };

     fetchConfig();
   }, []);
   ```

3. **Save config on button click:**

   ```tsx
   const handleSave = async () => {
     try {
       const result = await API.graphql(
         graphqlOperation(updateChatConfigMutation, {
           requireAuth: config.chat_require_auth,
           primaryModel: config.chat_primary_model,
           fallbackModel: config.chat_fallback_model,
           globalQuotaDaily: config.chat_global_quota_daily,
           perUserQuotaDaily: config.chat_per_user_quota_daily,
           themePreset: config.chat_theme_preset,
           themeOverrides: JSON.stringify(config.chat_theme_overrides || {}),
         })
       );

       if (result.data.updateChatConfig.success) {
         alert('Configuration saved successfully!');
       } else {
         alert(`Save failed: ${result.data.updateChatConfig.message}`);
       }
     } catch (error) {
       console.error('Save error:', error);
       alert('Failed to save configuration');
     }
   };
   ```

### Verification Checklist

- [ ] GraphQL queries defined
- [ ] Config fetched on component mount
- [ ] Save button calls updateChatConfig mutation
- [ ] Error handling for API failures
- [ ] Success/failure alerts shown to user

### Commit

```bash
git add src/ui/src/pages/Settings.tsx
git commit -m "feat(ui): connect Settings page to configuration API

- Add GraphQL queries for getChatConfig and updateChatConfig
- Fetch config on component mount
- Save config on button click
- Display success/error messages
- Handle API errors gracefully"
```

---

## Task 5: Add Unit Tests for ChatSettings

### Goal

Create unit tests for ChatSettings component.

### Files to Create

- `src/ui/src/components/ChatSettings.test.tsx`

### Instructions

Create `ChatSettings.test.tsx`:

```tsx
/**
 * Tests for ChatSettings component
 */
import { render, screen, fireEvent } from '@testing-library/react';
import { ChatSettings } from './ChatSettings';

describe('ChatSettings', () => {
  const mockConfig = {
    chat_require_auth: false,
    chat_primary_model: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
    chat_fallback_model: 'us.amazon.nova-micro-v1:0',
    chat_global_quota_daily: 10000,
    chat_per_user_quota_daily: 100,
    chat_theme_preset: 'light',
    chat_theme_overrides: {},
  };

  const mockOnUpdate = vi.fn();

  it('renders authentication toggle', () => {
    render(<ChatSettings config={mockConfig} onUpdate={mockOnUpdate} />);

    expect(screen.getByText(/Require Authentication/i)).toBeInTheDocument();
  });

  it('calls onUpdate when auth toggle changed', () => {
    render(<ChatSettings config={mockConfig} onUpdate={mockOnUpdate} />);

    const toggle = screen.getByRole('checkbox');
    fireEvent.click(toggle);

    expect(mockOnUpdate).toHaveBeenCalledWith('chat_require_auth', true);
  });

  it('renders model selectors', () => {
    render(<ChatSettings config={mockConfig} onUpdate={mockOnUpdate} />);

    expect(screen.getByText(/Primary Model/i)).toBeInTheDocument();
    expect(screen.getByText(/Fallback Model/i)).toBeInTheDocument();
  });

  it('renders quota inputs', () => {
    render(<ChatSettings config={mockConfig} onUpdate={mockOnUpdate} />);

    expect(screen.getByText(/Global Daily Quota/i)).toBeInTheDocument();
    expect(screen.getByText(/Per-User Daily Quota/i)).toBeInTheDocument();
  });

  it('displays embed code when CDN URL provided', () => {
    render(
      <ChatSettings
        config={mockConfig}
        cdnUrl="https://d123.cloudfront.net/amplify-chat.js"
        onUpdate={mockOnUpdate}
      />
    );

    expect(screen.getByText(/Embed on Your Website/i)).toBeInTheDocument();
    expect(screen.getByText(/Copy Embed Code/i)).toBeInTheDocument();
  });

  it('does not display embed code when CDN URL missing', () => {
    render(<ChatSettings config={mockConfig} onUpdate={mockOnUpdate} />);

    expect(screen.queryByText(/Embed on Your Website/i)).not.toBeInTheDocument();
  });
});
```

Run tests:
```bash
cd src/ui
npm test ChatSettings.test.tsx
```

### Commit

```bash
git add src/ui/src/components/ChatSettings.test.tsx
git commit -m "test(ui): add unit tests for ChatSettings component

- Test authentication toggle rendering and interaction
- Test model selectors display
- Test quota inputs display
- Test embed code conditional rendering
- Test copy button functionality"
```

---

## Phase 5 Complete - Final Verification

### Checklist

- [ ] All commits made with conventional commit format
- [ ] ChatSettings component created and styled
- [ ] Integrated into Settings page with conditional rendering
- [ ] Configuration API created (GraphQL mutation/query)
- [ ] UI wired to API for fetching and saving config
- [ ] Unit tests for ChatSettings component
- [ ] All TypeScript compiles without errors
- [ ] All tests pass

### End-to-End Integration Test

**Prerequisites:** All phases 1-4 deployed

**Test Flow:**

1. **Deploy with chat:**

   ```bash
   python publish.py --project-name final-test --admin-email admin@example.com --region us-east-1 --deploy-chat
   ```

   Save outputs (Admin UI URL, Chat CDN URL)

2. **Access Admin UI:**
   - Navigate to Admin UI URL from deployment output
   - Sign in with temporary password from email
   - Go to Settings page

3. **Verify chat settings visible:**
   - Should see "Chat Component Settings" section
   - Should see authentication toggle
   - Should see model selectors
   - Should see quota inputs
   - Should see embed code with CDN URL

4. **Test configuration changes:**
   - Toggle "Require Authentication" to ON
   - Change global quota to 50
   - Change theme to "dark"
   - Click "Save Configuration"
   - Should see success message

5. **Verify changes persisted:**
   - Refresh page
   - Settings should still show auth=ON, quota=50, theme=dark

6. **Test runtime effect:**
   - Open test HTML page with embedded chat
   - Send message without auth → should get "Authentication required" error
   - Add `user-id` and `user-token` attributes
   - Send message → should work
   - Send 51 messages → should switch to fallback model

7. **Verify in DynamoDB:**

   ```bash
   TABLE=$(aws cloudformation describe-stacks --stack-name RAGStack-final-test --query 'Stacks[0].Outputs[?OutputKey==`ConfigurationTableName`].OutputValue' --output text --region us-east-1)

   aws dynamodb get-item --table-name $TABLE --key '{"Configuration":{"S":"Default"}}' --region us-east-1

   # Verify:
   # chat_require_auth: true
   # chat_global_quota_daily: 50
   # chat_theme_preset: dark
   ```

---

## Common Issues

**Issue:** ChatSettings not appearing in UI
- **Solution:** Check `config.chat_deployed` is true. Verify Phase 3 set this flag.

**Issue:** "Configuration not found" error
- **Solution:** Ensure Phase 1's seeding ran. Check DynamoDB Default item exists.

**Issue:** Save button doesn't work
- **Solution:** Check GraphQL API is deployed. Verify Lambda has DynamoDB permissions.

**Issue:** Embed code shows "Deploying..."
- **Solution:** CDN URL not passed to component. Verify environment variable or API fetch.

**Issue:** Changes don't take effect in chat
- **Solution:** Config cache is 60s. Wait 1 minute or restart conversation Lambda.

---

## Project Complete! 🎉

### What You've Built

Across all 5 phases, you've implemented:

✅ **Phase 1: SAM Foundations**
- Extended ConfigurationTable with chat settings
- Added web component packaging function

✅ **Phase 2: Web Component**
- Built embeddable React component
- Created web component wrapper for framework-agnostic use
- Configured build pipeline with config injection

✅ **Phase 3: Amplify Infrastructure**
- Created CDN (CloudFront + S3)
- Added CodeBuild for automated deployment
- Integrated into publish.py deployment flow

✅ **Phase 4: Amplify Runtime Logic**
- Implemented conversation handler Lambda
- Added config reading with caching
- Built rate limiting with quota tracking
- Enabled model degradation (cost protection)
- Supported optional authentication

✅ **Phase 5: SAM UI**
- Created ChatSettings admin component
- Integrated into Settings page
- Built configuration API
- Enabled runtime config changes

### Final Deployment Command

```bash
python publish.py \
  --project-name production \
  --admin-email admin@yourcompany.com \
  --region us-east-1 \
  --deploy-chat
```

### Usage

**Embed on any website:**
```html
<script src="https://YOUR_CDN_URL/amplify-chat.js"></script>
<amplify-chat conversation-id="my-site"></amplify-chat>
```

**Manage settings:**
- Navigate to Admin UI → Settings
- Adjust models, quotas, themes
- Changes take effect in ~60 seconds

**Monitor costs:**
- Check CloudWatch metrics for quota usage
- Fallback model automatically prevents overages

---

**Congratulations!** The Amplify chat feature is complete and production-ready.
