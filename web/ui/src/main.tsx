import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { TooltipProvider } from '@/components/ui/tooltip'

// Follow the system theme. shadcn switches on a `dark` class.
const media = window.matchMedia('(prefers-color-scheme: dark)')
const sync = () => document.documentElement.classList.toggle('dark', media.matches)
sync()
media.addEventListener('change', sync)

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TooltipProvider>
      <App />
    </TooltipProvider>
  </StrictMode>,
)
