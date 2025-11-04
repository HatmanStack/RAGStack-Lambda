/**
 * Tests for validation utilities
 */
import { describe, it, expect } from 'vitest';
import {
  isValidHexColor,
  isValidFontFamily,
  isWithinRange,
  validateThemeOverrides,
  validateQuota,
} from './validation';

describe('isValidHexColor', () => {
  it('accepts valid 6-digit hex colors', () => {
    expect(isValidHexColor('#0073bb')).toBe(true);
    expect(isValidHexColor('#FFFFFF')).toBe(true);
    expect(isValidHexColor('#000000')).toBe(true);
    expect(isValidHexColor('#abc123')).toBe(true);
  });

  it('accepts valid 3-digit hex colors', () => {
    expect(isValidHexColor('#fff')).toBe(true);
    expect(isValidHexColor('#000')).toBe(true);
    expect(isValidHexColor('#a1b')).toBe(true);
  });

  it('accepts empty string (optional field)', () => {
    expect(isValidHexColor('')).toBe(true);
    expect(isValidHexColor(null)).toBe(true);
    expect(isValidHexColor(undefined)).toBe(true);
  });

  it('rejects invalid hex colors', () => {
    expect(isValidHexColor('0073bb')).toBe(false);  // Missing #
    expect(isValidHexColor('#gg0000')).toBe(false);  // Invalid character
    expect(isValidHexColor('#00')).toBe(false);      // Too short
    expect(isValidHexColor('#0000000')).toBe(false); // Too long
    expect(isValidHexColor('blue')).toBe(false);     // Color name
  });
});

describe('isValidFontFamily', () => {
  it('accepts valid CSS font families', () => {
    expect(isValidFontFamily('Inter')).toBe(true);
    expect(isValidFontFamily('Inter, system-ui, sans-serif')).toBe(true);
    expect(isValidFontFamily('"Helvetica Neue", Arial')).toBe(true);
    expect(isValidFontFamily("'Times New Roman', serif")).toBe(true);
    expect(isValidFontFamily('Roboto-Regular')).toBe(true);
  });

  it('accepts empty string (optional field)', () => {
    expect(isValidFontFamily('')).toBe(true);
    expect(isValidFontFamily(null)).toBe(true);
    expect(isValidFontFamily(undefined)).toBe(true);
  });

  it('rejects invalid font families', () => {
    expect(isValidFontFamily('font{family}')).toBe(false);  // Invalid characters
    expect(isValidFontFamily('font;family')).toBe(false);   // Semicolon
    expect(isValidFontFamily('font<script>')).toBe(false);  // XSS attempt
  });
});

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

describe('validateThemeOverrides', () => {
  it('accepts valid theme overrides', () => {
    const result = validateThemeOverrides({
      primaryColor: '#0073bb',
      fontFamily: 'Inter, sans-serif',
      spacing: 'comfortable',
    });

    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('accepts partial overrides', () => {
    const result = validateThemeOverrides({
      primaryColor: '#0073bb',
    });

    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('accepts empty object', () => {
    const result = validateThemeOverrides({});
    expect(result.valid).toBe(true);
  });

  it('accepts null/undefined', () => {
    expect(validateThemeOverrides(null).valid).toBe(true);
    expect(validateThemeOverrides(undefined).valid).toBe(true);
  });

  it('rejects invalid primary color', () => {
    const result = validateThemeOverrides({
      primaryColor: 'blue', // Not hex
    });

    expect(result.valid).toBe(false);
    expect(result.errors).toContain('Primary color must be a valid hex color (e.g., #0073bb)');
  });

  it('rejects invalid font family', () => {
    const result = validateThemeOverrides({
      fontFamily: 'font<script>',
    });

    expect(result.valid).toBe(false);
    expect(result.errors).toContain('Font family contains invalid characters');
  });

  it('rejects invalid spacing value', () => {
    const result = validateThemeOverrides({
      spacing: 'extra-wide', // Not in enum
    });

    expect(result.valid).toBe(false);
    expect(result.errors).toContain('Spacing must be one of: compact, comfortable, spacious');
  });

  it('reports multiple errors', () => {
    const result = validateThemeOverrides({
      primaryColor: 'invalid',
      fontFamily: 'bad;font',
      spacing: 'wrong',
    });

    expect(result.valid).toBe(false);
    expect(result.errors.length).toBeGreaterThan(1);
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
