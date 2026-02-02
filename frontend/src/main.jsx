import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import axios from 'axios'
import './index.css'
import { AuthProvider } from './auth/AuthProvider.jsx'
import { AppRoutes } from './AppRoutes.jsx'
import { AppHistoryProvider } from './navigation/AppHistoryProvider.jsx'

document.documentElement.classList.add('dark')
axios.defaults.timeout = 15000

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppHistoryProvider>
          <AppRoutes />
        </AppHistoryProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
