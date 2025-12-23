# RAGStack-Lambda Web UI

React-based admin interface for document upload, management, and search.

## Quick Start

```bash
npm install
npm run dev   # http://localhost:5173
```

## Prerequisites

- Node.js 24+
- SAM stack deployed
- AWS CLI configured
- `.env.local` with Cognito/AppSync credentials from SAM outputs

## Technology

- React 19, Vite 7
- Cloudscape Design System
- AWS AppSync GraphQL
- Cognito authentication

## Commands

| Command | Action |
|---------|--------|
| `npm run dev` | Dev server (localhost:5173) |
| `npm run build` | Production build |
| `npm run lint` | ESLint |
| `npm test` | Unit tests |

## Environment Variables

Create `.env.local` from SAM stack outputs:
```
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=us-east-1_XXXXXX
VITE_USER_POOL_CLIENT_ID=XXXXXX
VITE_IDENTITY_POOL_ID=us-east-1:XXXXXX
VITE_GRAPHQL_URL=https://XXXXXX.appsync-api.us-east-1.amazonaws.com/graphql
VITE_DATA_BUCKET=ragstack-data-XXXXXX
```

## Troubleshooting

See [docs/TROUBLESHOOTING.md](../../docs/TROUBLESHOOTING.md)
