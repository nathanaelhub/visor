import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { ClerkProvider } from '@clerk/react'
import App from './App.jsx'
import { CLERK_KEY } from './session.js'
import './theme.css'

// Sign-in is on only when a Clerk key is configured (spec 08); without one Visor is the plain demo.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    {CLERK_KEY
      ? <ClerkProvider publishableKey={CLERK_KEY} afterSignOutUrl="/"><App /></ClerkProvider>
      : <App />}
  </StrictMode>,
)
