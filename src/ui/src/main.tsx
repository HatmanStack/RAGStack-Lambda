import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Amplify } from 'aws-amplify'
import type { ResourcesConfig } from '@aws-amplify/core'
import '@cloudscape-design/global-styles/index.css'
import './index.css'
import App from './App.jsx'
import awsConfig from './config.js'

// Configure Amplify
Amplify.configure(awsConfig as ResourcesConfig)

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element not found');
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
