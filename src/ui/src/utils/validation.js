/**
 * Validation utilities for configuration fields
 *
 * Ensures values passed to chat component won't cause rendering issues.
 */

/**
 * Validate hex color format
 * @param {string} color - Color value to validate
 * @returns {boolean} True if valid hex color
 */
export function isValidHexColor(color) {
  if (!color) return true; // Empty is valid (optional)
  return /^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3})$/.test(color);
}

/**
 * Validate CSS font-family string
 * @param {string} fontFamily - Font family to validate
 * @returns {boolean} True if valid CSS font-family
 */
export function isValidFontFamily(fontFamily) {
  if (!fontFamily) return true; // Empty is valid (optional)

  // Basic validation: check for common CSS font-family patterns
  // Allow letters, numbers, spaces, hyphens, commas, and quotes
  return /^[\w\s\-,'"]+$/.test(fontFamily);
}

/**
 * Validate number is within range
 * @param {number} value - Number to validate
 * @param {number} min - Minimum value (inclusive)
 * @param {number} max - Maximum value (inclusive)
 * @returns {boolean} True if within range
 */
export function isWithinRange(value, min, max) {
  const num = Number(value);
  if (isNaN(num)) return false;
  if (min !== undefined && num < min) return false;
  if (max !== undefined && num > max) return false;
  return true;
}

/**
 * Validate chat theme overrides object
 * @param {object} overrides - Theme overrides to validate
 * @returns {{valid: boolean, errors: string[]}} Validation result
 */
export function validateThemeOverrides(overrides) {
  const errors = [];

  if (!overrides || typeof overrides !== 'object') {
    return { valid: true, errors: [] }; // Empty is valid
  }

  // Validate primaryColor
  if (overrides.primaryColor && !isValidHexColor(overrides.primaryColor)) {
    errors.push('Primary color must be a valid hex color (e.g., #0073bb)');
  }

  // Validate fontFamily
  if (overrides.fontFamily && !isValidFontFamily(overrides.fontFamily)) {
    errors.push('Font family contains invalid characters');
  }

  // Validate spacing enum
  if (overrides.spacing && !['compact', 'comfortable', 'spacious'].includes(overrides.spacing)) {
    errors.push('Spacing must be one of: compact, comfortable, spacious');
  }

  return {
    valid: errors.length === 0,
    errors
  };
}

/**
 * Validate quota value
 * @param {number} value - Quota value to validate
 * @returns {{valid: boolean, error: string|null}} Validation result
 */
export function validateQuota(value) {
  if (!isWithinRange(value, 1, 1000000)) {
    return {
      valid: false,
      error: 'Quota must be between 1 and 1,000,000'
    };
  }

  // Check if integer
  if (!Number.isInteger(Number(value))) {
    return {
      valid: false,
      error: 'Quota must be a whole number'
    };
  }

  return { valid: true, error: null };
}

/**
 * Validate budget threshold value
 * @param {number} value - Budget threshold in USD
 * @returns {{valid: boolean, error: string|null}} Validation result
 */
export function validateBudgetThreshold(value) {
  if (!isWithinRange(value, 1, 100000)) {
    return {
      valid: false,
      error: 'Budget must be between $1 and $100,000'
    };
  }

  // Check if integer
  if (!Number.isInteger(Number(value))) {
    return {
      valid: false,
      error: 'Budget must be a whole number'
    };
  }

  return { valid: true, error: null };
}
