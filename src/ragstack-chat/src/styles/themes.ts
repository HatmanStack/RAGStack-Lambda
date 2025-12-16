/**
 * Theme presets and CSS variable mapping
 * Phase 3: Comprehensive theme system with full color palettes
 */

export const THEME_PRESETS = {
  light: {
    // Background colors
    '--chat-color-bg': '#ffffff',
    '--chat-color-bg-secondary': '#f5f5f5',

    // Text colors
    '--chat-color-text': '#1a1a1a',
    '--chat-color-text-secondary': '#666666',

    // Border colors
    '--chat-color-border': '#d5d5d5',
    '--chat-color-border-light': '#e3e3e3',

    // Message colors
    '--chat-color-user-bg': '#0972d3',
    '--chat-color-user-text': '#ffffff',
    '--chat-color-assistant-bg': '#f5f5f5',
    '--chat-color-assistant-text': '#1a1a1a',

    // Source colors
    '--chat-color-source-bg': '#f8f9fa',
    '--chat-color-source-border': '#d5d5d5',
    '--chat-color-source-accent': '#0972d3',
  },
  dark: {
    // Background colors
    '--chat-color-bg': '#1a1a1a',
    '--chat-color-bg-secondary': '#2a2a2a',

    // Text colors
    '--chat-color-text': '#ffffff',
    '--chat-color-text-secondary': '#999999',

    // Border colors
    '--chat-color-border': '#333333',
    '--chat-color-border-light': '#2a2a2a',

    // Message colors
    '--chat-color-user-bg': '#0972d3',
    '--chat-color-user-text': '#ffffff',
    '--chat-color-assistant-bg': '#2a2a2a',
    '--chat-color-assistant-text': '#ffffff',

    // Source colors
    '--chat-color-source-bg': '#252525',
    '--chat-color-source-border': '#333333',
    '--chat-color-source-accent': '#539fe5',
  },
  brand: {
    // Background colors
    '--chat-color-bg': '#ffffff',
    '--chat-color-bg-secondary': '#fff8f0',

    // Text colors
    '--chat-color-text': '#1a1a1a',
    '--chat-color-text-secondary': '#666666',

    // Border colors
    '--chat-color-border': '#ffd280',
    '--chat-color-border-light': '#ffe4b3',

    // Message colors
    '--chat-color-user-bg': '#ff9900',
    '--chat-color-user-text': '#ffffff',
    '--chat-color-assistant-bg': '#fff8f0',
    '--chat-color-assistant-text': '#1a1a1a',

    // Source colors
    '--chat-color-source-bg': '#fffbf5',
    '--chat-color-source-border': '#ffd280',
    '--chat-color-source-accent': '#ff9900',
  },
} as const;

export type ThemePreset = keyof typeof THEME_PRESETS;

export interface ThemeOverrides {
  primaryColor?: string;
  backgroundColor?: string;
  textColor?: string;
  fontFamily?: string;
  spacing?: 'compact' | 'comfortable' | 'spacious';
}

/**
 * Storage key for persisting theme preferences
 */
const THEME_STORAGE_KEY = 'amplify-chat-theme';

/**
 * Apply theme to target element with preset and overrides
 *
 * IMPORTANT: Theme is scoped to the target element, not document root.
 * This allows multiple chat instances with different themes on same page.
 *
 * @param target - Element to apply theme to (REQUIRED for proper scoping)
 * @param preset - Theme preset to apply (light, dark, brand)
 * @param overrides - Optional theme overrides for customization
 */
export function applyTheme(
  target: HTMLElement,
  preset: ThemePreset = 'light',
  overrides?: ThemeOverrides
) {
  if (!target) {
    console.warn('applyTheme: target element is required for proper theme scoping');
    return;
  }

  // Apply preset colors
  const presetVars = THEME_PRESETS[preset] || THEME_PRESETS.light;
  Object.entries(presetVars).forEach(([key, value]) => {
    target.style.setProperty(key, value);
  });

  // Apply spacing preset
  if (overrides?.spacing) {
    const spacingMap = {
      compact: {
        '--chat-spacing-xs': '2px',
        '--chat-spacing-sm': '4px',
        '--chat-spacing-md': '8px',
        '--chat-spacing-lg': '12px',
        '--chat-spacing-xl': '16px',
        '--chat-spacing-xxl': '20px',
      },
      comfortable: {
        '--chat-spacing-xs': '4px',
        '--chat-spacing-sm': '8px',
        '--chat-spacing-md': '12px',
        '--chat-spacing-lg': '16px',
        '--chat-spacing-xl': '20px',
        '--chat-spacing-xxl': '24px',
      },
      spacious: {
        '--chat-spacing-xs': '6px',
        '--chat-spacing-sm': '12px',
        '--chat-spacing-md': '16px',
        '--chat-spacing-lg': '24px',
        '--chat-spacing-xl': '32px',
        '--chat-spacing-xxl': '40px',
      },
    };

    const spacingVars = spacingMap[overrides.spacing];
    if (spacingVars && typeof spacingVars === 'object') {
      Object.entries(spacingVars).forEach(([key, value]) => {
        target.style.setProperty(key, value);
      });
    } else {
      console.warn(`Invalid spacing preset: "${overrides.spacing}". Expected: compact, comfortable, or spacious.`);
    }
  }

  // Apply custom overrides (highest priority)
  if (overrides?.primaryColor) {
    target.style.setProperty('--chat-color-user-bg', overrides.primaryColor);
    target.style.setProperty('--chat-color-source-accent', overrides.primaryColor);
  }

  if (overrides?.backgroundColor) {
    target.style.setProperty('--chat-color-bg', overrides.backgroundColor);
  }

  if (overrides?.textColor) {
    target.style.setProperty('--chat-color-text', overrides.textColor);
  }

  if (overrides?.fontFamily) {
    target.style.setProperty('--chat-font-family', overrides.fontFamily);
  }

  // Persist theme preference to sessionStorage
  saveThemePreference(preset, overrides);
}

/**
 * Save theme preference to sessionStorage
 */
export function saveThemePreference(preset: ThemePreset, overrides?: ThemeOverrides) {
  try {
    const themeData = {
      preset,
      overrides: overrides || {},
      timestamp: Date.now(),
    };
    sessionStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(themeData));
  } catch (error) {
    console.warn('Failed to save theme preference:', error);
  }
}

/**
 * Load theme preference from sessionStorage
 */
export function loadThemePreference(): { preset: ThemePreset; overrides?: ThemeOverrides } | null {
  try {
    const stored = sessionStorage.getItem(THEME_STORAGE_KEY);
    if (!stored) return null;

    const themeData = JSON.parse(stored);

    // Validate preset
    if (!THEME_PRESETS[themeData.preset as ThemePreset]) {
      return null;
    }

    return {
      preset: themeData.preset as ThemePreset,
      overrides: themeData.overrides,
    };
  } catch (error) {
    console.warn('Failed to load theme preference:', error);
    return null;
  }
}

/**
 * Clear theme preference from sessionStorage
 */
export function clearThemePreference() {
  try {
    sessionStorage.removeItem(THEME_STORAGE_KEY);
  } catch (error) {
    console.warn('Failed to clear theme preference:', error);
  }
}
