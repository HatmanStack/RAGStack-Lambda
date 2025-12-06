import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.ts'],
    include: [
      'tests/**/*.test.ts',
      'tests/**/*.test.tsx',
      'src/**/__tests__/**/*.test.ts',
      'src/**/__tests__/**/*.test.tsx',
    ],
    // Exclude integration tests from default run - they require deployed backend
    // Run integration tests separately with: npm test -- --include '**/integration/**'
    exclude: [
      'node_modules/**',
      '**/integration/**',
    ],
  },
});
