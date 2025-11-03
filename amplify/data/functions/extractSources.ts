/**
 * Extract and format source citations from Bedrock RetrieveAndGenerate response
 *
 * This function is called by Bedrock after generating a response.
 * It parses the raw citation data and formats it for frontend display.
 */

export async function extractSources(input: {
  citations?: Array<{
    title?: string;
    location?: {
      characterOffsets?: Array<{ start: number; end: number }>;
      pageNumber?: number;
    };
    sourceContent?: Array<{
      text?: string;
    }>;
  }>;
}): Promise<{
  sources: Array<{
    title: string;
    location: string;
    snippet: string;
  }>;
}> {
  try {
    // Default: no sources found
    if (!input.citations || input.citations.length === 0) {
      return { sources: [] };
    }

    // Process each citation
    const sources = input.citations
      .map((citation) => {
        try {
          // Get document title (required)
          const title = citation.title || 'Unknown Document';

          // Format location (page number or character offset)
          let location = 'Unknown Location';
          if (citation.location?.pageNumber) {
            location = `Page ${citation.location.pageNumber}`;
          } else if (citation.location?.characterOffsets?.[0]) {
            const offset = citation.location.characterOffsets[0];
            location = `Characters ${offset.start}-${offset.end}`;
          }

          // Extract snippet from source content (first 200 characters)
          let snippet = '';
          if (citation.sourceContent && citation.sourceContent.length > 0) {
            const text = citation.sourceContent
              .map((content) => content.text || '')
              .join(' ')
              .trim();
            snippet = text.substring(0, 200);
            if (text.length > 200) {
              snippet += '...';
            }
          }

          return {
            title,
            location,
            snippet: snippet || '(No content available)',
          };
        } catch (error) {
          console.error('Failed to process citation:', error);
          return null;
        }
      })
      .filter((source) => source !== null) // Remove failed entries
      // Remove duplicates by title (some citations might repeat)
      .filter((source, index, array) => {
        return array.findIndex((s) => s.title === source.title) === index;
      }) as Array<{
        title: string;
        location: string;
        snippet: string;
      }>;

    return { sources };
  } catch (error) {
    console.error('extractSources failed:', error);
    return { sources: [] };
  }
}
