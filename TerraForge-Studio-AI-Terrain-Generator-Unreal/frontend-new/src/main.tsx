import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './styles/index.css'
import './styles/mobile.css'
import { ThemeProvider } from './contexts/ThemeContext'
import ToastContainer from './components/ToastContainer'
import ErrorBoundary from './components/ErrorBoundary'
import './i18n/config'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <App />
        <ToastContainer />
      </ThemeProvider>
    </ErrorBoundary>
  </React.StrictMode>,
)

