● Section 6: UI Implementation & Build Process

  Key Finding: This repository has dramatically simplified the UI, reducing from 67 components (15,896 LOC) to 18 components (2,285 LOC) - an 86% reduction - while modernizing to React 19 and
  maintaining core functionality.

  Technology Stack Comparison:
  | Technology     | This Repository                | Base Repository          | Modernization?         |
  |----------------|--------------------------------|--------------------------|------------------------|
  | React          | 19.1.1 (latest)                | 18.3.1 (LTS)             | ✓ Yes - React 19       |
  | React Router   | 7.9.4                          | 6.28.0                   | ✓ Yes - v7             |
  | Build Tool     | Vite 7.1.7                     | Vite 7.1.10              | Same generation        |
  | Test Framework | Vitest 4.0.5 + explicit config | Vitest (implicit)        | ✓ Yes - better testing |
  | ESLint         | 9.36.0 (flat config)           | 8.57.1 (extended config) | ✓ Yes - ESLint 9       |
  | Amplify        | 6.15.7 (v6 API)                | 6.15.0 (v6 API)          | Same generation        |
  | CloudScape     | 3.0.1118                       | 3.0.1112                 | Same design system     |

  Code Complexity Reduction:
  - JSX Files: 18 vs 67 (74% fewer files)
  - Total Lines: 2,285 vs 15,896 (86% less code)
  - Dependencies: ~40 vs ~60 (33% fewer packages)
  - Component Directories: 6 vs 19 (68% fewer directories)

  UI Architecture:

  This Repository (Simple, focused):
  src/ui/src/
  ├── components/
  │   ├── Auth/           (Login, AuthProvider, RequireAuth)
  │   ├── Dashboard/      (DocumentTable, DocumentDetail modal)
  │   ├── Layout/         (AppLayout, Navigation)
  │   ├── Search/         (SearchInterface, SearchResults)
  │   ├── Settings/       (Settings page)
  │   └── Upload/         (UploadZone drag-drop, UploadQueue)
  ├── hooks/
  │   ├── useDocuments.js (Fetch document list)
  │   ├── useSearch.js    (KB search logic)
  │   └── useUpload.js    (S3 presigned upload)
  └── App.jsx (Simple routing: /, /upload, /search, /settings)

  Base Repository (Complex, feature-rich):
  src/ui/src/
  ├── components/ (19 directories)
  │   ├── chat-panel/              # AI chat interface
  │   ├── configuration-layout/    # Settings management
  │   ├── discovery/               # Document discovery
  │   ├── document-agents-layout/  # Agent management
  │   ├── document-viewers/        # Multiple viewer types
  │   ├── step-function-flow/      # Execution visualization
  │   └── ...14 more directories
  ├── hooks/ (8 custom hooks)
  │   ├── use-configuration.js (22KB - complex state)
  │   ├── use-graphql-api.js   (14KB - wrapper)
  │   ├── use-parameter-store.js
  │   └── ...5 more hooks
  └── Complex nested routing (5 route files)

  Features Comparison:

  This Repository (5 core pages):
  1. Dashboard - Document list with CloudScape table, status badges, detail modal
  2. Upload - Drag-drop zone with progress tracking, S3 presigned URLs
  3. Search - Knowledge Base search interface with markdown results
  4. Settings - Configuration management (re-embedding, etc.)
  5. Login - Cognito authentication

  Base Repository (15+ pages/sections):
  - All of the above PLUS:
  - Advanced analytics with Chart.js visualizations
  - AI chat panel (sidebar, integrated)
  - Monaco code editor for document viewing
  - Step Function execution flow visualization
  - HITL (Human-in-the-Loop) workflow management
  - Sentiment analysis with trend indicators
  - Advanced document attribute mapping
  - Multi-viewer document viewers
  - Parameter Store configuration UI

  AWS Integration Approach:

  This Repository (Modern Amplify v6):
  // src/config.js - Clean, environment-variable based
  import { Amplify } from 'aws-amplify';

  const awsConfig = {
    Auth: {
      Cognito: {
        userPoolId: import.meta.env.VITE_USER_POOL_ID,
        userPoolClientId: import.meta.env.VITE_USER_POOL_CLIENT_ID,
        // Modern Amplify v6 structure
      }
    },
    API: {
      GraphQL: {
        endpoint: import.meta.env.VITE_GRAPHQL_URL,
        defaultAuthMode: 'userPool'
      }
    }
  };

  Base Repository (Legacy aws-exports format):
  // aws-exports.js - Traditional awsmobile format
  const awsmobile = {
    aws_project_region: "us-east-1",
    aws_cognito_identity_pool_id: "...",
    aws_user_pools_id: "...",
    aws_appsync_graphqlEndpoint: "...",
    // Legacy Amplify format
  };

  Build Configuration:

  This Repository (vite.config.js):
  // Minimal, relies on Vite defaults
  export default defineConfig({
    plugins: [react()],
  });
  // Output: dist/

  Base Repository (vite.config.js):
  // Comprehensive with optimization
  export default defineConfig({
    plugins: [react(), svgr()],  // SVG as React components
    build: {
      outDir: 'build/',
      rollupOptions: {
        output: {
          manualChunks: {
            'aws-amplify': [...],      // Vendor chunking
            'aws-sdk': [...],
            'cloudscape': [...],
            'chart': [...],
            'react-vendor': [...]
          }
        }
      }
    },
    resolve: { alias: { '@': './src' } },  // Path alias
  });

  Unique Dependencies:

  Base Repository Only:
  - chart.js + react-chartjs-2 - Analytics visualizations
  - @monaco-editor/react - Code editor for document viewing
  - mammoth - Word document parsing
  - xlsx - Excel parsing
  - react-icons - Icon library
  - axios - HTTP client
  - dompurify - HTML sanitization
  - js-yaml - YAML parsing

  This Repository: Removed all of these, keeping only core dependencies for simplified use case

  Testing Configuration:

  This Repository (vitest.config.js):
  // Explicit test configuration
  export default defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/setupTests.js',
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html'],
      }
    }
  });

  Scripts: test, test:watch, test:ui, test:coverage

  Base Repository:
  - No explicit vitest.config.js
  - Single test script
  - Less comprehensive testing setup

  Development Experience:

  | Aspect                 | This Repository     | Base Repository               |
  |------------------------|---------------------|-------------------------------|
  | Hot Module Replacement | Vite default (fast) | Vite default (fast)           |
  | Dev Server Port        | 5173 (Vite default) | 3000 (customized)             |
  | TypeScript             | No                  | No                            |
  | Code Splitting         | Automatic           | Manual chunks (optimized)     |
  | Source Maps            | Not configured      | Inline (dev), disabled (prod) |
  | SVG Imports            | CSS/HTML only       | React components (SVGR)       |
  | Path Aliases           | None                | @ -> ./src                    |

  Build Output:
  - This Repository: dist/ (Vite standard)
  - Base Repository: build/ (Create React App convention)

  Verdict: The UI simplification is 100% intentional. This repository modernized to React 19, streamlined to 5 core pages, removed advanced features (analytics, chat, advanced viewers), and
  adopted cleaner Amplify v6 patterns. The base repository's complexity supports enterprise features (HITL workflows, analytics dashboards, chat interface) not needed for the focused OCR-to-KB
  use case.

  No Unintentional Divergences Found in UI implementation - all changes appear deliberate and aligned with the simplified scope.
