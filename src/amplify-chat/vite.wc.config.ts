import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite configuration for building the Web Component UMD bundle
 *
 * This builds src/wc.ts into a UMD bundle that can be used with:
 * <script src="path/to/amplify-chat.js"></script>
 * <amplify-chat conversation-id="my-chat"></amplify-chat>
 */

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: path.resolve(__dirname, 'src/wc.ts'),
      name: 'AmplifyChat',
      fileName: (format) => `wc.${format === 'umd' ? 'umd' : 'esm'}.js`,
    },
    rollupOptions: {
      external: [],
      output: [
        // UMD format for <script> tag usage
        {
          format: 'umd',
          file: 'dist/wc.js',
          name: 'AmplifyChat',
          globals: {},
        },
        // ES Module format for npm imports
        {
          format: 'es',
          file: 'dist/wc.esm.js',
        },
      ],
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
