import axios from 'axios'

const BASE = '/api'

const client = axios.create({ baseURL: BASE, timeout: 15000 })

export interface TicketInput {
  ticket_id?: string
  ticket_text: string
  category?: string
  confidence?: number
}

export interface ProcessResult {
  ticket_id: string
  category: string
  confidence: number
  action: 'auto_resolved' | 'draft_response' | 'escalated'
  resolution: {
    action: string
    confidence_tier: string
    resolution?: string
    draft?: string
    source_article?: string
    summary?: { issue_summary: string; probable_root_cause: string; priority: string; attempted_fixes: string }
    recommendations?: any[]
    timestamp: string
    confidence_score: number
  }
  recommendations: Array<{ rank: number; article_title: string; score: number }>
  timestamp: string
  latency_ms: number
}

export interface LiveMetrics {
  total_tickets_today: number
  auto_resolved: number
  escalated: number
  draft_responses: number
  active_users: number
  auto_resolution_rate: number
  escalation_rate: number
  categories: Record<string, number>
}

export interface TrendingItem {
  category: string
  score: number
  is_spike: boolean
  window: string
}

export interface ActivityItem {
  id: string
  ticket_id: string
  category: string
  action: string
  confidence: number
  timestamp: string
}

export interface EscalationItem {
  ticket_id: string
  ticket_text: string
  category: string
  confidence_score: number
  issue_summary: string
  attempted_fixes: string
  probable_root_cause: string
  priority: 'high' | 'medium' | 'low'
  recommended_articles: Array<{ title: string; score: number }>
  status: string
  created_at: string
}

export const api = {
  processTicket: (data: TicketInput) =>
    client.post<ProcessResult>('/copilot/process', data).then(r => r.data),

  agentSearch: (message: string, session_id?: string) =>
    client.post('/agent/search', { message, session_id }).then(r => r.data),

  getLiveMetrics: () =>
    client.get<LiveMetrics>('/analytics/live').then(r => r.data),

  getDashboard: () =>
    client.get('/analytics/dashboard').then(r => r.data),

  getHourlyTrend: (hours = 12) =>
    client.get(`/analytics/trend?hours=${hours}`).then(r => r.data),

  getActivityFeed: (count = 20) =>
    client.get<ActivityItem[]>(`/analytics/activity-feed?count=${count}`).then(r => r.data),

  getKbPerformance: () =>
    client.get('/analytics/kb-performance').then(r => r.data),

  getTrending: (window = '1h') =>
    client.get(`/trending?window=${window}`).then(r => r.data),

  getEscalationQueue: () =>
    client.get('/escalation/queue').then(r => r.data),

  claimEscalation: (agent_name: string) =>
    client.post('/escalation/claim', { agent_name }).then(r => r.data),

  getRecentConversations: () =>
    client.get('/conversations/recent').then(r => r.data),

  getConversation: (id: string) =>
    client.get(`/conversation/${id}`).then(r => r.data),

  getSampleTickets: () =>
    client.get('/demo/sample-tickets').then(r => r.data),

  batchProcess: (tickets: any[]) =>
    client.post('/demo/batch', { tickets }).then(r => r.data),

  resetDemo: () =>
    client.post('/demo/reset', {}).then(r => r.data),

  healthCheck: () =>
    client.get('/').then(r => r.data),
}
