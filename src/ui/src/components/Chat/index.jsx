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
    ? `<script src="${cdnUrl}"></script>\n<ragstack-chat conversation-id="my-site"></ragstack-chat>`
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
            <ExpandableSection
              headerText="Embed Chat on Your Website"
              variant="footer"
            >
              <SpaceBetween size="s">
                <Box variant="p">
                  Add this chat component to any HTML page by copying the code below:
                </Box>
                <Box>
                  <code
                    style={{
                      display: 'block',
                      whiteSpace: 'pre-wrap',
                      padding: '12px',
                      background: 'var(--color-background-container-content)',
                      border: '1px solid var(--color-border-divider-default)',
                      borderRadius: '4px',
                      fontFamily: 'monospace',
                    }}
                  >
                    {embedCode}
                  </code>
                </Box>
                <CopyToClipboard
                  copyText={embedCode}
                  copyButtonText="Copy Embed Code"
                  copySuccessText="Copied!"
                />
                <Box variant="small" color="text-body-secondary">
                  The chat component works with any framework: React, Vue, Angular, Svelte, or plain HTML.
                </Box>
              </SpaceBetween>
            </ExpandableSection>
          </Container>
        )}
      </SpaceBetween>
    </ContentLayout>
  );
}
