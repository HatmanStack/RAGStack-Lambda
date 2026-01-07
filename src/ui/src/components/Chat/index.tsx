import React, { useState, useEffect, useMemo } from 'react';
import {
  ContentLayout,
  Header,
  SpaceBetween,
  Container,
  Box,
  CopyToClipboard,
  ExpandableSection,
  Tabs,
  Textarea,
  Button,
  FormField,
  Alert,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { updateConfiguration } from '../../graphql/mutations/updateConfiguration';
import type { GqlResponse } from '../../types/graphql';
import { ChatPanel } from './ChatPanel';

interface ConfigData {
  Default: string;
  Custom: string;
}

const DEFAULT_SYSTEM_PROMPT = 'You are a helpful assistant that answers questions based on information from a knowledge base. Always base your answers on the provided knowledge base information. If the provided information doesn\'t contain the answer, clearly state that and provide what relevant information you can. Be concise but thorough.';

export function Chat() {
  const [cdnUrl, setCdnUrl] = useState(null);
  const [requireAuth, setRequireAuth] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [originalPrompt, setOriginalPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'success' | 'error' | null>(null);
  const client = useMemo(() => generateClient(), []);

  useEffect(() => {
    async function loadConfig() {
      try {
        const response = await client.graphql({ query: getConfiguration }) as GqlResponse;
        const config = response.data?.getConfiguration as ConfigData | undefined;
        const parsedDefault = JSON.parse(config?.Default || '{}');
        const parsedCustom = JSON.parse(config?.Custom || '{}');
        const merged = { ...parsedDefault, ...parsedCustom };
        setCdnUrl(merged.chat_cdn_url || null);
        setRequireAuth(merged.chat_require_auth || false);
        const prompt = merged.chat_system_prompt || DEFAULT_SYSTEM_PROMPT;
        setSystemPrompt(prompt);
        setOriginalPrompt(prompt);
      } catch (err) {
        console.error('Error loading config:', err);
      }
    }
    loadConfig();
  }, [client]);

  const handleSavePrompt = async () => {
    setIsSaving(true);
    setSaveStatus(null);
    try {
      await client.graphql({
        query: updateConfiguration,
        variables: { customConfig: JSON.stringify({ chat_system_prompt: systemPrompt }) }
      });
      setOriginalPrompt(systemPrompt);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      console.error('Error saving config:', err);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  };

  const hasPromptChanged = systemPrompt !== originalPrompt;

  const cdnPlaceholder = cdnUrl || 'https://your-cdn-url/ragstack-chat.js';

  const basicEmbed = `<script src="${cdnPlaceholder}"></script>
<ragstack-chat conversation-id="my-site"></ragstack-chat>`;

  const authEmbed = `<script src="${cdnPlaceholder}"></script>
<ragstack-chat
  conversation-id="my-site"
  user-id="USER_ID"
  user-token="COGNITO_JWT_TOKEN"
></ragstack-chat>

<script>
// Get token from your auth provider (Cognito, Auth0, etc.)
async function initChat() {
  const token = await getAuthToken(); // Your auth logic
  const userId = getCurrentUserId();  // Your user ID

  const chat = document.querySelector('ragstack-chat');
  chat.setAttribute('user-token', token);
  chat.setAttribute('user-id', userId);
}
initChat();
</script>`;

  return (
    <ContentLayout
      header={
        <Header
          variant="h1"
          description="Ask questions about your documents using natural language"
        >
          Knowledge Base Chat
        </Header>
      }
    >
      <SpaceBetween size="l">
        <ChatPanel />

        <Container>
          <ExpandableSection headerText="System Prompt" variant="footer">
            <SpaceBetween size="m">
              <FormField
                label="Chat System Prompt"
                description="This prompt defines how the AI assistant responds to questions. Changes take effect immediately for new conversations."
              >
                <Textarea
                  value={systemPrompt}
                  onChange={({ detail }) => setSystemPrompt(detail.value)}
                  rows={5}
                  placeholder="Enter the system prompt for the chat assistant..."
                />
              </FormField>
              <SpaceBetween direction="horizontal" size="xs">
                <Button
                  variant="primary"
                  onClick={handleSavePrompt}
                  loading={isSaving}
                  disabled={!hasPromptChanged}
                >
                  Save
                </Button>
                <Button
                  variant="link"
                  onClick={() => setSystemPrompt(originalPrompt)}
                  disabled={!hasPromptChanged || isSaving}
                >
                  Cancel
                </Button>
              </SpaceBetween>
              {saveStatus === 'success' && (
                <Alert type="success" dismissible onDismiss={() => setSaveStatus(null)}>
                  System prompt saved successfully.
                </Alert>
              )}
              {saveStatus === 'error' && (
                <Alert type="error" dismissible onDismiss={() => setSaveStatus(null)}>
                  Failed to save system prompt. Please try again.
                </Alert>
              )}
            </SpaceBetween>
          </ExpandableSection>
        </Container>

        <Container>
          <ExpandableSection headerText="Embed Chat Widget" variant="footer">
              <SpaceBetween size="m">
                <Box variant="small" color="text-body-secondary">
                  Add to any HTML page. Works with React, Vue, Angular, Svelte, or plain HTML.
                  {requireAuth && (
                    <Box color="text-status-warning" padding={{ top: 'xs' }}>
                      <strong>Authentication required:</strong> Your current settings require user authentication.
                    </Box>
                  )}
                </Box>

                <Tabs
                  activeTabId={activeTab}
                  onChange={({ detail }) => setActiveTab(detail.activeTabId)}
                  tabs={[
                    {
                      id: 'basic',
                      label: 'Basic (Public)',
                      content: (
                        <SpaceBetween size="s">
                          <Box variant="small" color="text-body-secondary">
                            For public access when authentication is disabled.
                          </Box>
                          <code
                            style={{
                              display: 'block',
                              whiteSpace: 'pre-wrap',
                              padding: '12px',
                              background: '#1a1a2e',
                              color: '#e6e6e6',
                              borderRadius: '6px',
                              fontFamily: "'Fira Code', monospace",
                              fontSize: '12px',
                            }}
                          >
                            {basicEmbed}
                          </code>
                          <CopyToClipboard
                            textToCopy={basicEmbed}
                            copyButtonText="Copy"
                            copySuccessText="Copied!"
                            copyErrorText="Failed to copy"
                            variant="icon"
                          />
                        </SpaceBetween>
                      ),
                    },
                    {
                      id: 'auth',
                      label: 'Authenticated',
                      content: (
                        <SpaceBetween size="s">
                          <Box variant="small" color="text-body-secondary">
                            Pass user credentials from your auth provider (Cognito, Auth0, etc.)
                          </Box>
                          <code
                            style={{
                              display: 'block',
                              whiteSpace: 'pre-wrap',
                              padding: '12px',
                              background: '#1a1a2e',
                              color: '#e6e6e6',
                              borderRadius: '6px',
                              fontFamily: "'Fira Code', monospace",
                              fontSize: '12px',
                              maxHeight: '300px',
                              overflow: 'auto',
                            }}
                          >
                            {authEmbed}
                          </code>
                          <CopyToClipboard
                            textToCopy={authEmbed}
                            copyButtonText="Copy"
                            copySuccessText="Copied!"
                            copyErrorText="Failed to copy"
                            variant="icon"
                          />
                        </SpaceBetween>
                      ),
                    },
                  ]}
                />
              </SpaceBetween>
          </ExpandableSection>
        </Container>
      </SpaceBetween>
    </ContentLayout>
  );
}
