import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Amplify } from 'aws-amplify'
import '@cloudscape-design/global-styles/index.css'
import './index.css'
import App from './App.jsx'
import awsConfig from './config.js'

// Configure Amplify
// eslint-disable-next-line @typescript-eslint/no-explicit-any
Amplify.configure(awsConfig as any)

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
