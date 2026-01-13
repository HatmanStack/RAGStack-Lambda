/**
 * Validation utilities for configuration fields
 */

interface ValidationResult {
  valid: boolean;
  error: string | null;
}

/**
 * Validate number is within range
 * @param value - Number to validate
 * @param min - Minimum value (inclusive)
 * @param max - Maximum value (inclusive)
 * @returns True if within range
 */
export function isWithinRange(value: number | string, min?: number, max?: number): boolean {
  const num = Number(value);
  if (isNaN(num)) return false;
  if (min !== undefined && num < min) return false;
  if (max !== undefined && num > max) return false;
  return true;
}

/**
 * Validate quota value
 * @param value - Quota value to validate
 * @returns Validation result
 */
export function validateQuota(value: number | string): ValidationResult {
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
 * @param value - Budget threshold in USD
 * @returns Validation result
 */
export function validateBudgetThreshold(value: number | string): ValidationResult {
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
