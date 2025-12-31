/**
 * Tests for validation utilities
 */
import { describe, it, expect } from 'vitest';
import {
  isWithinRange,
  validateQuota,
} from './validation';

describe('isWithinRange', () => {
  it('validates numbers within range', () => {
    expect(isWithinRange(50, 0, 100)).toBe(true);
    expect(isWithinRange(0, 0, 100)).toBe(true);   // Min boundary
    expect(isWithinRange(100, 0, 100)).toBe(true); // Max boundary
  });

  it('rejects numbers outside range', () => {
    expect(isWithinRange(-1, 0, 100)).toBe(false);
    expect(isWithinRange(101, 0, 100)).toBe(false);
  });

  it('handles undefined min/max', () => {
    expect(isWithinRange(50, undefined, 100)).toBe(true);
    expect(isWithinRange(50, 0, undefined)).toBe(true);
    expect(isWithinRange(50, undefined, undefined)).toBe(true);
  });

  it('rejects non-numbers', () => {
    expect(isWithinRange('not a number', 0, 100)).toBe(false);
    expect(isWithinRange(NaN, 0, 100)).toBe(false);
  });
});

describe('validateQuota', () => {
  it('accepts valid quotas', () => {
    expect(validateQuota(100).valid).toBe(true);
    expect(validateQuota(10000).valid).toBe(true);
    expect(validateQuota(1).valid).toBe(true);       // Min boundary
    expect(validateQuota(1000000).valid).toBe(true); // Max boundary
  });

  it('rejects quotas below minimum', () => {
    const result = validateQuota(0);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('between 1 and 1,000,000');
  });

  it('rejects quotas above maximum', () => {
    const result = validateQuota(1000001);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('between 1 and 1,000,000');
  });

  it('rejects non-integer values', () => {
    const result = validateQuota(100.5);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('whole number');
  });

  it('rejects negative values', () => {
    const result = validateQuota(-100);
    expect(result.valid).toBe(false);
  });
});
