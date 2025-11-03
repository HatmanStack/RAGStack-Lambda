import { describe, it, expect } from 'vitest';
import { extractSources } from './extractSources';

describe('extractSources function', () => {
  /**
   * Test 1: No citations provided
   */
  it('returns empty array when no citations provided', async () => {
    const result = await extractSources({});
    expect(result.sources).toEqual([]);

    const result2 = await extractSources({ citations: [] });
    expect(result2.sources).toEqual([]);
  });

  /**
   * Test 2: Single citation with all fields
   */
  it('extracts source with all fields', async () => {
    const result = await extractSources({
      citations: [
        {
          title: 'README.md',
          location: { pageNumber: 1 },
          sourceContent: [{ text: 'This is sample documentation' }],
        },
      ],
    });

    expect(result.sources).toHaveLength(1);
    expect(result.sources[0]).toEqual({
      title: 'README.md',
      location: 'Page 1',
      snippet: 'This is sample documentation',
    });
  });

  /**
   * Test 3: Citation with character offset (no page number)
   */
  it('formats character offset when page number unavailable', async () => {
    const result = await extractSources({
      citations: [
        {
          title: 'document.pdf',
          location: {
            characterOffsets: [{ start: 100, end: 200 }],
          },
          sourceContent: [{ text: 'Some content here' }],
        },
      ],
    });

    expect(result.sources[0].location).toBe('Characters 100-200');
  });

  /**
   * Test 4: Long snippet gets truncated
   */
  it('truncates long snippets to 200 characters', async () => {
    const longText = 'A'.repeat(300); // 300 characters

    const result = await extractSources({
      citations: [
        {
          title: 'document.pdf',
          location: { pageNumber: 1 },
          sourceContent: [{ text: longText }],
        },
      ],
    });

    expect(result.sources[0].snippet).toHaveLength(203); // 200 + '...'
    expect(result.sources[0].snippet.endsWith('...')).toBe(true);
  });

  /**
   * Test 5: Duplicate citations are removed
   */
  it('removes duplicate sources by title', async () => {
    const result = await extractSources({
      citations: [
        {
          title: 'document.pdf',
          location: { pageNumber: 1 },
          sourceContent: [{ text: 'First mention' }],
        },
        {
          title: 'document.pdf', // Same title
          location: { pageNumber: 2 },
          sourceContent: [{ text: 'Second mention' }],
        },
        {
          title: 'other.pdf',
          location: { pageNumber: 1 },
          sourceContent: [{ text: 'Different document' }],
        },
      ],
    });

    expect(result.sources).toHaveLength(2); // 2 unique titles
    const titles = result.sources.map((s) => s.title);
    expect(titles).toContain('document.pdf');
    expect(titles).toContain('other.pdf');
  });

  /**
   * Test 6: Missing fields handled gracefully
   */
  it('handles missing fields with defaults', async () => {
    const result = await extractSources({
      citations: [
        {
          // No title
          // No location
          // No sourceContent
        },
      ],
    });

    expect(result.sources[0]).toEqual({
      title: 'Unknown Document',
      location: 'Unknown Location',
      snippet: '(No content available)',
    });
  });

  /**
   * Test 7: Multiple content blocks are joined
   */
  it('joins multiple source content blocks', async () => {
    const result = await extractSources({
      citations: [
        {
          title: 'document.pdf',
          location: { pageNumber: 1 },
          sourceContent: [
            { text: 'First part' },
            { text: 'Second part' },
            { text: 'Third part' },
          ],
        },
      ],
    });

    expect(result.sources[0].snippet).toContain('First part');
    expect(result.sources[0].snippet).toContain('Second part');
  });
});
