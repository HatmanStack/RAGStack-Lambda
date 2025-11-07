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
      formats: ['umd', 'es'],
      fileName: (format) => `wc.${format === 'umd' ? 'js' : 'esm.js'}`,
    },
    rollupOptions: {
      external: [],
      output: {
        // UMD format configuration
        name: 'AmplifyChat',
        globals: {},
      },
    },
    outDir: 'dist',
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
