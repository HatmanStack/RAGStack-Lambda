/**
 * Validation utilities for configuration fields
 */

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
