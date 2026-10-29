import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { ConnectionProvider } from './api/connection'
import { CanvasPage } from './canvas/CanvasPage'
import { ChoiceDialogProvider } from './components/ChoiceDialog'
import { HealthLights } from './components/HealthLights'
import { StatusBar } from './components/StatusBar'
import { ToastProvider } from './components/Toast'
import { LearnPage } from './pages/LearnPage'
import { ProjectList } from './pages/ProjectList'

const queryClient = new QueryClient({ defaultOptions: { queries: { staleTime: 2000, retry: 1 } } })

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ConnectionProvider>
        <ToastProvider>
          <ChoiceDialogProvider>
            <BrowserRouter>
              <StatusBar />
              <Routes>
                <Route path="/" element={<ProjectList />} />
                <Route path="/p/:pid" element={<CanvasPage />} />
                <Route path="/hoc" element={<LearnPage />} />
              </Routes>
              <HealthLights />
            </BrowserRouter>
          </ChoiceDialogProvider>
        </ToastProvider>
      </ConnectionProvider>
    </QueryClientProvider>
  )
}
