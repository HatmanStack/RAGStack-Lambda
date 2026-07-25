import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    server: {
      deps: {
        // These two packages ship ESM whose relative imports carry no file
        // extension ("./base-component/component-metadata"), which only a
        // bundler can resolve. Vitest externalises node_modules by default and
        // hands them to Node's ESM loader, which requires the extension and
        // throws ERR_MODULE_NOT_FOUND. Inlining routes them through Vite's
        // resolver instead. Scoped to these two rather than all of
        // @cloudscape-design/ because inlining the components package as well
        // makes the suite an order of magnitude slower.
        inline: [
          /@cloudscape-design\/component-toolkit/,
          /@cloudscape-design\/collection-hooks/,
        ],
      },
    },
    setupFiles: ['./src/setupTests.ts'],
    css: true,
    testTimeout: process.env.CI ? 60000 : 15000,
    retry: process.env.CI ? 1 : 0,
    include: ['src/**/*.{test,spec}.{js,ts,jsx,tsx}'],
    coverage: {
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        'src/setupTests.ts',
      ]
    }
  },
});
