# RAGStack-Lambda UI

React-based web interface for RAGStack-Lambda serverless document processing system.

## Features

- **Authentication** - Cognito-backed login/signup with Amplify UI Authenticator
- **Document Upload** - Drag-and-drop file upload with progress tracking
- **Document Dashboard** - Table view with filtering, sorting, pagination, and detail modal
- **Knowledge Base Search** - Search interface with expandable results and markdown rendering
- **Responsive Layout** - Built with AWS Cloudscape Design System

## Technology Stack

- **React 19** - Latest React with modern patterns
- **Vite 7** - Fast build tool and dev server
- **AWS Amplify v6** - AWS integration (Auth, API, Storage)
- **Cloudscape Design System v3** - AWS design system components
- **React Router v7** - Client-side routing
- **React Markdown** - Markdown rendering for search results

## Prerequisites

- Node.js 24+ (installed via nvm)
- CloudFormation stack deployed (Phases 0-4)
- AWS CLI configured

## Setup

### 1. Install Dependencies

```bash
cd src/ui
npm install
```

### 2. Configure AWS Resources

After deploying the CloudFormation stack, run the configuration script:

```bash
# From project root
./scripts/configure_ui.sh <stack-name>

# Example:
./scripts/configure_ui.sh RAGStack-dev
```

This script:
- Fetches CloudFormation outputs
- Creates `.env.local` with AWS resource IDs
- Validates all required outputs are present

### 3. Start Development Server

```bash
npm start
# or
npm run dev
```

The UI will be available at http://localhost:5173

## Manual Configuration

If you prefer to configure manually, copy `.env.template` to `.env.local` and fill in values:

```bash
cp .env.template .env.local
# Edit .env.local with your CloudFormation outputs
```

Required environment variables:
- `VITE_AWS_REGION` - AWS region (e.g., us-east-1)
- `VITE_USER_POOL_ID` - Cognito User Pool ID
- `VITE_USER_POOL_CLIENT_ID` - Cognito User Pool Client ID
- `VITE_IDENTITY_POOL_ID` - Cognito Identity Pool ID
- `VITE_GRAPHQL_URL` - AppSync GraphQL API endpoint
- `VITE_INPUT_BUCKET` - S3 input bucket name

## Project Structure

```
src/ui/
├── src/
│   ├── components/
│   │   ├── Auth/           # Authentication components
│   │   ├── Dashboard/      # Document dashboard
│   │   ├── Upload/         # File upload interface
│   │   ├── Search/         # Knowledge Base search
│   │   └── Layout/         # App layout and navigation
│   ├── hooks/              # Custom React hooks
│   │   ├── useUpload.js
│   │   ├── useDocuments.js
│   │   └── useSearch.js
│   ├── config.js           # AWS Amplify configuration
│   ├── App.jsx             # Main app component
│   └── main.jsx            # Entry point
├── .env.template           # Environment variable template
├── .env.local              # Local environment config (gitignored)
├── package.json
└── vite.config.js
```

## Available Scripts

- `npm start` / `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Usage

### Authentication

1. Navigate to http://localhost:5173
2. You'll be redirected to `/login`
3. Sign up with email or sign in if you have an account
4. Verify email (check inbox for verification code)
5. After login, you'll be redirected to the dashboard

### Uploading Documents

1. Click "Upload" in the sidebar
2. Drag and drop files or click to browse
3. Supported formats: PDF, JPG, PNG, TIFF, DOCX, XLSX, TXT, CSV, MD, EPUB
4. Watch progress in the upload queue
5. Files are automatically uploaded to S3 and processing begins

### Viewing Documents

1. Click "Dashboard" in the sidebar
2. View all documents in the table
3. Use search box to filter documents
4. Click filename to view detailed information
5. Table refreshes automatically every 30 seconds

### Searching Knowledge Base

1. Click "Search" in the sidebar
2. Enter a question or search term
3. Click "Search" or press Enter
4. View results with relevance scores
5. Expand results to see full content and sources

## Development

### Adding New Components

Follow the existing patterns:
- Place components in `src/components/<Feature>/`
- Create custom hooks in `src/hooks/`
- Use Cloudscape Design System components
- Follow Amplify v6 patterns for AWS integration

### GraphQL Queries

Use inline `gql` template literals with `graphql-tag`:

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

- Use React hooks (`useState`, `useEffect`, `useCallback`)
- Create custom hooks for reusable logic
- Use context for global state (e.g., `AuthProvider`)

## Troubleshooting

### Build Errors

If you see build errors:
1. Delete `node_modules` and `package-lock.json`
2. Run `npm install` again
3. Clear Vite cache: `rm -rf node_modules/.vite`

### Authentication Issues

If authentication fails:
1. Verify `.env.local` has correct Cognito IDs
2. Check Cognito User Pool settings in AWS Console
3. Ensure email verification is configured

### API Errors

If GraphQL queries fail:
1. Verify AppSync URL in `.env.local`
2. Check CloudWatch logs for Lambda errors
3. Ensure Cognito user has proper IAM permissions

## Production Build

Build for production deployment:

```bash
npm run build
```

Output will be in `dist/` directory. Deploy to:
- S3 + CloudFront (recommended)
- Amplify Hosting
- Any static hosting service

## Notes

- The UI polls for document updates every 30 seconds
- Large files (>50MB) may take several minutes to process
- Search requires documents to be fully indexed (status: INDEXED)
- All uploads are authenticated with Cognito credentials

## Support

For issues or questions:
- Check CloudWatch logs for backend errors
- Review CloudFormation stack outputs
- Ensure all AWS services are properly configured
