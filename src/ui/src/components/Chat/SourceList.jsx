import React from 'react';
import { Box, ExpandableSection } from '@cloudscape-design/components';

export function SourceList({ sources }) {
  // Early return if no sources
  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <ExpandableSection
      headerText={`Sources (${sources.length})`}
      variant="footer"
    >
      <Box variant="small">
        {sources.map((source) => (
          <Box
            key={`${source.documentId}-${source.pageNumber || 0}`}
            padding={{ bottom: 's' }}
          >
            <Box variant="strong">{source.documentId}</Box>

            {source.pageNumber && (
              <Box variant="small" color="text-body-secondary">
                Page {source.pageNumber}
              </Box>
            )}

            {source.snippet && (
              <Box variant="small" color="text-body-secondary">
                "{source.snippet}"...
              </Box>
            )}
          </Box>
        ))}
      </Box>
    </ExpandableSection>
  );
}
