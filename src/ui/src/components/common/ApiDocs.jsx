import React, { useState } from 'react';
import {
  Box,
  SpaceBetween,
  Tabs,
  CopyToClipboard,
  ExpandableSection,
  Container,
} from '@cloudscape-design/components';

const codeStyle = {
  display: 'block',
  whiteSpace: 'pre-wrap',
  padding: '12px',
  background: '#1a1a2e',
  color: '#e6e6e6',
  border: 'none',
  borderRadius: '6px',
  fontFamily: "'Fira Code', 'Monaco', 'Consolas', monospace",
  fontSize: '12px',
  lineHeight: '1.5',
  overflow: 'auto',
  maxHeight: '300px',
};

const CodeBlock = ({ code, copyLabel = 'Copy' }) => (
  <Box>
    <code style={codeStyle}>{code}</code>
    <Box padding={{ top: 'xs' }}>
      <CopyToClipboard
        copyText={code}
        copyButtonText={copyLabel}
        copySuccessText="Copied!"
        variant="inline"
      />
    </Box>
  </Box>
);

export const ApiDocs = ({
  title = 'API Access',
  description,
  endpoint,
  examples = [],
  footer,
}) => {
  const [activeTab, setActiveTab] = useState(examples[0]?.id || 'graphql');

  const tabs = examples.map((ex) => ({
    id: ex.id,
    label: ex.label,
    content: <CodeBlock code={ex.code} copyLabel={`Copy ${ex.label}`} />,
  }));

  return (
    <Container>
      <ExpandableSection headerText={title} variant="footer">
        <SpaceBetween size="m">
          {description && (
            <Box variant="small" color="text-body-secondary">
              {description}
            </Box>
          )}

          {endpoint && (
            <Box>
              <Box variant="awsui-key-label" padding={{ bottom: 'xxs' }}>
                Endpoint
              </Box>
              <SpaceBetween direction="horizontal" size="xs" alignItems="center">
                <code
                  style={{
                    padding: '4px 8px',
                    background: '#1a1a2e',
                    color: '#e6e6e6',
                    borderRadius: '4px',
                    fontFamily: 'monospace',
                    fontSize: '12px',
                    wordBreak: 'break-all',
                  }}
                >
                  {endpoint}
                </code>
                <CopyToClipboard
                  copyText={endpoint}
                  copyButtonText="Copy"
                  copySuccessText="Copied!"
                  variant="inline"
                />
              </SpaceBetween>
            </Box>
          )}

          {tabs.length > 0 && (
            <Tabs
              activeTabId={activeTab}
              onChange={({ detail }) => setActiveTab(detail.activeTabId)}
              tabs={tabs}
            />
          )}

          {footer && (
            <Box variant="small" color="text-body-secondary">
              {footer}
            </Box>
          )}
        </SpaceBetween>
      </ExpandableSection>
    </Container>
  );
};
