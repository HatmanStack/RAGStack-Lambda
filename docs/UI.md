# React Web UI

The web interface for RAGStack-Lambda document upload and management.

## Quick Setup

```bash
cd src/ui
npm install
npm start  # http://localhost:5173
```

## Technology Stack

- **React 19** - UI framework
- **Vite 7** - Build tool
- **AWS Amplify v6** - AWS integration
- **Cloudscape Design System** - AWS design components
- **React Router v7** - Routing

## Features

- **Authentication** - Cognito-backed login/signup
- **Document Upload** - Drag-and-drop with progress tracking
- **Document Dashboard** - Table with filtering, sorting, pagination
- **Chat Interface** - Query documents via AI chat (requires --deploy-chat)
- **Responsive** - Works on desktop, tablet, mobile

## Configuration

### Environment Variables

After deploying the SAM stack, configure `.env.local`:

```bash
VITE_AWS_REGION=us-east-1
VITE_USER_POOL_ID=us-east-1_xxxxx
VITE_USER_POOL_CLIENT_ID=xxxxx
VITE_IDENTITY_POOL_ID=us-east-1:xxxxx
VITE_GRAPHQL_URL=https://xxxxx.appsync-api.us-east-1.amazonaws.com/graphql
VITE_DATA_BUCKET=ragstack-xxxxx-data-xxxxx
```

Or use the configuration script:
```bash
./scripts/configure_ui.sh RAGStack-<project-name>
```

## Project Structure

```
src/ui/
├── src/
│   ├── components/
│   │   ├── Auth/          # Authentication
│   │   ├── Dashboard/     # Document management
│   │   ├── Upload/        # File upload
│   │   ├── Chat/          # AI chat interface
│   │   ├── Settings/      # Configuration
│   │   └── Layout/        # Navigation and layout
│   ├── hooks/             # Custom React hooks
│   ├── config.js          # Amplify configuration
│   ├── App.jsx            # Main component
│   └── main.jsx           # Entry point
├── package.json
└── vite.config.js
```

## Commands

```bash
npm start / npm run dev   # Development server
npm run build             # Production build
npm run preview           # Preview production build
npm run lint              # ESLint
npm test                  # Vitest unit tests
```

## Development Guide

### Adding Components

1. Create in `src/components/<Feature>/`
2. Create custom hooks in `src/hooks/`
3. Use Cloudscape Design System components
4. Follow Amplify v6 patterns

### GraphQL Queries

```javascript
import { generateClient } from 'aws-amplify/api';
import gql from 'graphql-tag';

const QUERY = gql`
  query MyQuery {
    field
  }
`;

const client = generateClient();
const { data } = await client.graphql({ query: QUERY });
```

### State Management

Use React hooks and custom hooks for logic. Context for global state.

## Troubleshooting

**Build errors**: Delete `node_modules`, `package-lock.json`, run `npm install`

**Auth issues**: Verify `.env.local` has correct Cognito IDs

**API errors**: Check AppSync URL and Lambda CloudWatch logs

**UI not loading**: Invalidate CloudFront cache: `aws cloudfront create-invalidation --distribution-id <ID> --paths "/*"`

## Related Documentation

- [Development Guide](DEVELOPMENT.md) - Development patterns and commands
- [Architecture](ARCHITECTURE.md) - How the system works
- [Deployment](DEPLOYMENT.md) - How to deploy to AWS
- [Troubleshooting](TROUBLESHOOTING.md) - Common issues
