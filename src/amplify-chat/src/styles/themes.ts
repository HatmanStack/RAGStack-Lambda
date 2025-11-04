/**
 * Theme presets and CSS variable mapping
 */

export const THEME_PRESETS = {
  light: {
    '--chat-bg-primary': '#ffffff',
    '--chat-bg-secondary': '#f5f5f5',
    '--chat-color-primary': '#0073bb',
    '--chat-color-text': '#16191f',
    '--chat-color-border': '#e0e0e0',
  },
  dark: {
    '--chat-bg-primary': '#16191f',
    '--chat-bg-secondary': '#232f3e',
    '--chat-color-primary': '#539fe5',
    '--chat-color-text': '#ffffff',
    '--chat-color-border': '#414d5c',
  },
  brand: {
    '--chat-bg-primary': '#ffffff',
    '--chat-bg-secondary': '#f0f8ff',
    '--chat-color-primary': '#ff9900',
    '--chat-color-text': '#16191f',
    '--chat-color-border': '#ffd280',
  },
} as const;

export type ThemePreset = keyof typeof THEME_PRESETS;

export interface ThemeOverrides {
  primaryColor?: string;
  fontFamily?: string;
  spacing?: 'compact' | 'comfortable' | 'spacious';
}

/**
 * Apply theme to document root
 */
export function applyTheme(preset: ThemePreset = 'light', overrides?: ThemeOverrides) {
  const root = document.documentElement;

  // Apply preset
  const presetVars = THEME_PRESETS[preset] || THEME_PRESETS.light;
  Object.entries(presetVars).forEach(([key, value]) => {
    root.style.setProperty(key, value);
  });

  // Apply overrides
  if (overrides?.primaryColor) {
    root.style.setProperty('--chat-color-primary', overrides.primaryColor);
  }

  if (overrides?.fontFamily) {
    root.style.setProperty('--chat-font-family', overrides.fontFamily);
  }

  if (overrides?.spacing) {
    const spacingMap = {
      compact: '0.5rem',
      comfortable: '1rem',
      spacious: '1.5rem',
    };
    root.style.setProperty('--chat-spacing', spacingMap[overrides.spacing]);
  }
}
