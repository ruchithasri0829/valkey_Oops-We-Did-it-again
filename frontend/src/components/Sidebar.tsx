import { useEffect } from 'react'
import { useStore } from '../store/useStore'
import { api } from '../services/api'
import {
  LayoutDashboard, Ticket, Bot, Flame, AlertOctagon,
  MessageSquare, BarChart3, Zap
} from 'lucide-react'

const NAV = [
  { id: 'dashboard',   label: 'AI Operations',       icon: LayoutDashboard },
  { id: 'submit',      label: 'Resolution Workspace', icon: Ticket },
  { id: 'agent',       label: 'Agentic Search',       icon: Bot },
  { id: 'trending',    label: 'Incident Analytics',   icon: Flame },
  { id: 'escalation',  label: 'Escalation Queue',     icon: AlertOctagon },
  { id: 'conversations', label: 'Conversations',      icon: MessageSquare },
  { id: 'kb',          label: 'KB Insights',          icon: BarChart3 },
  { id: 'demo',        label: 'Demo Controls',        icon: Zap },
]

export function Sidebar() {
  const { activePage, setActivePage, apiConnected, escalationQueueLength, setEscalationQueueLength } = useStore()

  // Fetch actual queue length on mount and periodically
  useEffect(() => {
    const fetchQueue = async () => {
      try {
        const d = await api.getEscalationQueue()
        setEscalationQueueLength(d.stats?.pending || 0)
      } catch {}
    }
    fetchQueue()
    const id = setInterval(fetchQueue, 8000)
    return () => clearInterval(id)
  }, [setEscalationQueueLength])

  return (
    <aside style={{
      width: 240,
      minHeight: '100vh',
      background: 'linear-gradient(180deg, #0d0720 0%, #1a0a2e 100%)',
      borderRight: '1px solid rgba(123,47,190,0.2)',
      display: 'flex',
      flexDirection: 'column',
      padding: '20px 12px',
      flexShrink: 0,
    }}>
      {/* Logo */}
      <div style={{ textAlign: 'center', marginBottom: 28, padding: '0 8px' }}>
        <div style={{ fontSize: '1.6rem', marginBottom: 4 }}>⚡</div>
        <div style={{ fontWeight: 800, fontSize: '0.95rem', color: '#ede7f6', letterSpacing: 0.5 }}>
          AI Support Copilot
        </div>
        <div style={{
          background: '#7B2FBE', color: 'white',
          padding: '2px 10px', borderRadius: 20,
          fontSize: '0.65rem', fontWeight: 700,
          letterSpacing: 1, marginTop: 6, display: 'inline-block',
        }}>
          POWERED BY VALKEY
        </div>
      </div>

      {/* Status dot */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px', marginBottom: 8 }}>
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: apiConnected ? '#00e676' : '#ff1744',
          boxShadow: apiConnected ? '0 0 8px #00e676' : '0 0 8px #ff1744',
        }} />
        <span style={{ fontSize: '0.75rem', color: '#9575cd' }}>
          {apiConnected ? 'API Connected' : 'API Offline'}
        </span>
      </div>

      {/* Nav */}
      <nav style={{ flex: 1 }}>
        {NAV.map(({ id, label, icon: Icon }) => (
          <div
            key={id}
            className={`nav-item ${activePage === id ? 'active' : ''}`}
            onClick={() => setActivePage(id)}
          >
            <Icon size={16} />
            <span>{label}</span>
            {id === 'escalation' && escalationQueueLength > 0 && (
              <span style={{
                marginLeft: 'auto', background: '#ff1744',
                color: 'white', borderRadius: 10,
                padding: '1px 7px', fontSize: '0.7rem', fontWeight: 700,
              }}>
                {escalationQueueLength}
              </span>
            )}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '12px 14px', borderTop: '1px solid rgba(123,47,190,0.2)', marginTop: 8 }}>
        <div style={{ fontSize: '0.7rem', color: '#6b5b8a', lineHeight: 1.6 }}>
          Build Beyond Limits<br />
          React Hyderabad Hackathon<br />
          <span style={{ color: '#7B2FBE' }}>valkey/valkey-bundle:9-alpine</span>
        </div>
      </div>
    </aside>
  )
}
