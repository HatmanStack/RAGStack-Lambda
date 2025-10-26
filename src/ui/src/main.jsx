import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Amplify } from 'aws-amplify'
import '@cloudscape-design/global-styles/index.css'
import './index.css'
import App from './App.jsx'
import awsConfig from './config.js'

// Configure Amplify
Amplify.configure(awsConfig)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
