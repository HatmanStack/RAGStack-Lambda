import React, { useState, useEffect, useMemo } from 'react';
import {
  ContentLayout,
  Header,
  SpaceBetween,
  Container,
  Box,
  CopyToClipboard,
  ExpandableSection,
} from '@cloudscape-design/components';
import { generateClient } from 'aws-amplify/api';
import { getConfiguration } from '../../graphql/queries/getConfiguration';
import { ChatPanel } from './ChatPanel';

export function Chat() {
  const [cdnUrl, setCdnUrl] = useState(null);
  const client = useMemo(() => generateClient(), []);

  useEffect(() => {
    async function loadCdnUrl() {
      try {
        const response = await client.graphql({ query: getConfiguration });
        const config = response.data.getConfiguration;
        const parsedDefault = JSON.parse(config.Default);
        const parsedCustom = JSON.parse(config.Custom || '{}');
        const merged = { ...parsedDefault, ...parsedCustom };
        setCdnUrl(merged.chat_cdn_url || null);
      } catch (err) {
        console.error('Error loading CDN URL:', err);
      }
    }
    loadCdnUrl();
  }, [client]);

  const embedCode = cdnUrl
    ? `<script src="${cdnUrl}"></script>
<ragstack-chat conversation-id="my-site"></ragstack-chat>`
    : null;

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

        {cdnUrl && (
          <Container>
            <ExpandableSection headerText="Embed Chat Widget" variant="footer">
              <SpaceBetween size="s">
                <Box variant="small" color="text-body-secondary">
                  Add to any HTML page. Works with React, Vue, Angular, Svelte, or plain HTML.
                </Box>
                <Box>
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
                    {embedCode}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={embedCode}
                  copyButtonText="Copy Embed Code"
                  copySuccessText="Copied!"
                  variant="inline"
                />
              </SpaceBetween>
            </ExpandableSection>
          </Container>
        )}
      </SpaceBetween>
    </ContentLayout>
  );
}
