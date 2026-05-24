import { useEffect } from 'react'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Sidebar } from './components/Sidebar'
import { Dashboard } from './pages/Dashboard'
import { SubmitTicket } from './pages/SubmitTicket'
import { AgentSearch } from './pages/AgentSearch'
import { TrendingIncidents } from './pages/TrendingIncidents'
import { EscalationQueue } from './pages/EscalationQueue'
import { Conversations } from './pages/Conversations'
import { KbPerformance } from './pages/KbPerformance'
import { DemoControls } from './pages/DemoControls'
import { useStore } from './store/useStore'
import { api } from './services/api'
import { useTawkTo } from './hooks/useTawkTo'

const PAGES: Record<string, React.ComponentType> = {
  dashboard:     Dashboard,
  submit:        SubmitTicket,
  agent:         AgentSearch,
  trending:      TrendingIncidents,
  escalation:    EscalationQueue,
  conversations: Conversations,
  kb:            KbPerformance,
  demo:          DemoControls,
}

export default function App() {
  const { activePage, setApiConnected } = useStore()

  // Initialize Tawk.to (hidden by default, shown only on escalation)
  useTawkTo()

  useEffect(() => {
    api.healthCheck()
      .then(() => setApiConnected(true))
      .catch(() => setApiConnected(false))
  }, [setApiConnected])

  const Page = PAGES[activePage] || Dashboard

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', minHeight: '100vh' }}>
        <Sidebar />
        <main style={{ flex: 1, overflowY: 'auto', maxHeight: '100vh' }}>
          <Page />
        </main>
      </div>
    </ErrorBoundary>
  )
}
