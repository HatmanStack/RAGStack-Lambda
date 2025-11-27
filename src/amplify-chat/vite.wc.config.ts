import { defineConfig, Plugin } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Custom plugin to inject CSS into IIFE bundle
 * Vite doesn't automatically inject CSS in library mode IIFE builds,
 * so we need to do it manually.
 */
function injectCssPlugin(): Plugin {
  let cssContent = '';

  return {
    name: 'inject-css',
    apply: 'build',
    generateBundle(options, bundle) {
      // Collect CSS from any .css files
      for (const fileName in bundle) {
        const chunk = bundle[fileName];
        if (chunk.type === 'asset' && fileName.endsWith('.css')) {
          cssContent += chunk.source;
          // Remove the CSS file from the bundle (we'll inline it)
          delete bundle[fileName];
        }
      }

      // Inject CSS into the JS bundle
      if (cssContent) {
        for (const fileName in bundle) {
          const chunk = bundle[fileName];
          if (chunk.type === 'chunk' && chunk.isEntry) {
            // Prepend CSS injection code to the bundle
            const cssInjection = `(function(){var s=document.createElement('style');s.textContent=${JSON.stringify(cssContent)};document.head.appendChild(s);})();`;
            chunk.code = cssInjection + chunk.code;
          }
        }
      }
    },
  };
}

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
  plugins: [react(), injectCssPlugin()],
  define: {
    // Replace Node.js globals with browser-compatible values
    'process.env.NODE_ENV': JSON.stringify('production'),
    'process.env': '{}',
    'global': 'globalThis',
  },
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/wc.ts'),
      name: 'AmplifyChat',
      fileName: (format) => `wc.${format === 'es' ? 'esm.' : ''}js`,
      formats: ['iife', 'es'],
    },
    cssCodeSplit: false,  // Inline all CSS into the JS bundle
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
  css: {
    modules: {
      localsConvention: 'camelCase',  // Convert CSS class names to camelCase for JS
    },
  },
});
