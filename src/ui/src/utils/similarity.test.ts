import { describe, it, expect } from 'vitest';
import { calculateSimilarity, findSimilarKeys } from './similarity';

describe('calculateSimilarity', () => {
  it('returns 1.0 for exact match', () => {
    expect(calculateSimilarity('topic', 'topic')).toBe(1);
  });

  it('returns 1.0 for case-insensitive match', () => {
    expect(calculateSimilarity('Topic', 'topic')).toBe(1);
    expect(calculateSimilarity('TOPIC', 'topic')).toBe(1);
  });

  it('returns low score for completely different strings', () => {
    const similarity = calculateSimilarity('abc', 'xyz');
    expect(similarity).toBeLessThan(0.5);
  });

  it('returns high score for similar strings', () => {
    const similarity = calculateSimilarity('doc_type', 'document_type');
    expect(similarity).toBeGreaterThan(0.6);
  });

  it('handles empty strings', () => {
    expect(calculateSimilarity('', '')).toBe(1);
    expect(calculateSimilarity('test', '')).toBe(0);
    expect(calculateSimilarity('', 'test')).toBe(0);
  });

  it('handles whitespace', () => {
    expect(calculateSimilarity(' topic ', 'topic')).toBe(1);
  });
});

describe('findSimilarKeys', () => {
  const existingKeys = ['document_type', 'topic', 'author', 'date_created'];

  it('finds similar keys above threshold', () => {
    const results = findSimilarKeys('doc_type', existingKeys, 0.6);
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].keyName).toBe('document_type');
  });

  it('returns empty array when no similar keys', () => {
    const results = findSimilarKeys('xyz123', existingKeys);
    expect(results).toEqual([]);
  });

  it('respects threshold parameter', () => {
    // With high threshold, should find fewer matches
    const highThreshold = findSimilarKeys('doc_type', existingKeys, 0.95);
    const lowThreshold = findSimilarKeys('doc_type', existingKeys, 0.5);
    expect(highThreshold.length).toBeLessThanOrEqual(lowThreshold.length);
  });

  it('sorts results by similarity descending', () => {
    const results = findSimilarKeys('topic', ['topic_name', 'topics', 'top'], 0.5);
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].similarity).toBeGreaterThanOrEqual(results[i].similarity);
    }
  });

  it('excludes exact matches', () => {
    const results = findSimilarKeys('topic', ['topic', 'topics', 'topic_name'], 0.5);
    const exactMatch = results.find((r) => r.keyName === 'topic');
    expect(exactMatch).toBeUndefined();
  });

  it('uses default threshold of 0.7', () => {
    // "date" vs "date_created" - similarity depends on implementation
    const results = findSimilarKeys('date', existingKeys);
    // Should use 0.7 threshold by default
    results.forEach((r) => {
      expect(r.similarity).toBeGreaterThanOrEqual(0.7);
    });
  });
});
