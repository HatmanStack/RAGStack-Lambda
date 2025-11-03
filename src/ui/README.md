# RAGStack-Lambda Web UI

React-based web interface for document upload, management, and search.

## Quick Start

```bash
npm install
npm start
# http://localhost:5173
```

## Full Documentation

See [docs/UI.md](../../docs/UI.md) for:
- Setup and configuration
- Project structure
- Development guide
- Troubleshooting
- Technology stack details

## Prerequisites

- Node.js 24+
- SAM stack deployed
- AWS CLI configured
- `.env.local` with credentials (see docs/UI.md)

## Technology

- React 19, Vite 7
- AWS Amplify v6, Cloudscape Design System
- GraphQL via AWS AppSync
- Cognito authentication

## Available Commands

```bash
npm start / npm run dev   # Dev server
npm run build             # Production build
npm run lint              # ESLint
npm test                  # Unit tests
```

## Features

- Document upload (drag-and-drop)
- Document management dashboard
- Knowledge Base search
- Real-time status tracking
- Responsive design

## Troubleshooting

Check [docs/UI.md](../../docs/UI.md#troubleshooting) and [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)

## Contributing

See [docs/DEVELOPMENT.md](../../docs/DEVELOPMENT.md)
