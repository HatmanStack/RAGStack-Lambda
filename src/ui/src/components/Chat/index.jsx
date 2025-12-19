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
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { ChatPanel } from './ChatPanel';

export function Chat() {
  const [cdnUrl, setCdnUrl] = useState(null);
  const [requireAuth, setRequireAuth] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const client = useMemo(() => generateClient(), []);

  useEffect(() => {
    async function loadConfig() {
      try {
        const response = await client.graphql({ query: getConfiguration });
        const config = response.data.getConfiguration;
        const parsedDefault = JSON.parse(config.Default);
        const parsedCustom = JSON.parse(config.Custom || '{}');
        const merged = { ...parsedDefault, ...parsedCustom };
        setCdnUrl(merged.chat_cdn_url || null);
        setRequireAuth(merged.chat_require_auth || false);
      } catch (err) {
        console.error('Error loading config:', err);
      }
    }
    loadConfig();
  }, [client]);

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
                            copyText={basicEmbed}
                            copyButtonText="Copy"
                            copySuccessText="Copied!"
                            variant="inline"
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
                            copyText={authEmbed}
                            copyButtonText="Copy"
                            copySuccessText="Copied!"
                            variant="inline"
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
