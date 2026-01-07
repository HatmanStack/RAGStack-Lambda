import { distance } from 'fastest-levenshtein';

export interface SimilarKey {
  keyName: string;
  similarity: number;
}

/**
 * Calculate similarity between two strings using Levenshtein distance.
 * Returns a value between 0 (completely different) and 1 (identical).
 */
export function calculateSimilarity(a: string, b: string): number {
  const normalizedA = a.toLowerCase().trim();
  const normalizedB = b.toLowerCase().trim();

  const maxLen = Math.max(normalizedA.length, normalizedB.length);
  if (maxLen === 0) return 1;

  const dist = distance(normalizedA, normalizedB);
  return 1 - dist / maxLen;
}

/**
 * Find keys from existingKeys that are similar to the input key.
 * Excludes exact matches (case-insensitive).
 * Returns results sorted by similarity descending.
 *
 * @param input - The key to check
 * @param existingKeys - Array of existing keys to compare against
 * @param threshold - Minimum similarity score (0-1), defaults to 0.7
 */
export function findSimilarKeys(
  input: string,
  existingKeys: string[],
  threshold = 0.7
): SimilarKey[] {
  const normalizedInput = input.toLowerCase().trim();

  const results: SimilarKey[] = [];

  for (const key of existingKeys) {
    const normalizedKey = key.toLowerCase().trim();

    // Skip exact matches
    if (normalizedKey === normalizedInput) continue;

    const similarity = calculateSimilarity(input, key);

    if (similarity >= threshold) {
      results.push({ keyName: key, similarity });
    }
  }

  // Sort by similarity descending
  results.sort((a, b) => b.similarity - a.similarity);

  return results;
}
