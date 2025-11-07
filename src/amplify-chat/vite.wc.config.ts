import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite configuration for building the Web Component as an IIFE bundle
 *
 * This builds src/wc.ts into an IIFE (Immediately Invoked Function Expression)
 * that auto-executes when loaded via script tag, ensuring customElements.define() runs.
 *
 * Usage:
 * <script src="path/to/amplify-chat.js"></script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 */

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/wc.ts'),
      name: 'AmplifyChat',
      fileName: (format) => `wc.${format === 'es' ? 'esm.' : ''}js`,
      formats: ['iife', 'es'],  // Changed from ['umd', 'es'] to ['iife', 'es']
    },
    rollupOptions: {
      output: [
        // IIFE format for <script> tag usage (auto-executes)
        {
          format: 'iife',
          name: 'AmplifyChat',
          // Don't externalize dependencies - bundle everything for standalone use
          inlineDynamicImports: true,
        },
        // ES Module format for npm imports
        {
          format: 'es',
        },
      ],
      // Bundle all dependencies (React, Amplify, etc.) for standalone IIFE
      external: [],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
