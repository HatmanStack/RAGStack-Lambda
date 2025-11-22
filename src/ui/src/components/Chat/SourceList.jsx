import React from 'react';
import { Box, ExpandableSection, Link } from '@cloudscape-design/components';

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
        {sources.map((source, index) => (
          <Box
            key={`${source.documentId || source.title}-${source.pageNumber ?? 'no-page'}-${index}`}
            padding={{ bottom: 's' }}
          >
            <Box variant="strong">{source.title || source.documentId}</Box>

            {source.pageNumber != null && (
              <Box variant="small" color="text-body-secondary">
                Page {source.pageNumber}
              </Box>
            )}

            {source.location && source.pageNumber == null && (
               <Box variant="small" color="text-body-secondary">
                 {source.location}
               </Box>
             )}

            {source.snippet && (
              <Box variant="small" color="text-body-secondary">
                "{source.snippet}"...
              </Box>
            )}

            {source.documentUrl && (
               <Box variant="small" padding={{ top: 'xs' }}>
                 <Link href={source.documentUrl} external>
                   View Document
                 </Link>
               </Box>
            )}

            {source.documentAccessAllowed === false && !source.documentUrl && (
               <Box variant="small" color="text-body-secondary" padding={{ top: 'xs' }}>
                  <i>Document access disabled</i>
               </Box>
            )}
          </Box>
        ))}
      </Box>
    </ExpandableSection>
  );
}
