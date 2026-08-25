const BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export type ClaimNeedingAttention = {
  claim_id: string
  payer_id: number
  payer_name?: string
  patient_id?: number
  patient_name?: string
  amount: number
  risk_score: number
  primary_issue_type?: string | null
  primary_issue_severity?: string | null
}

export type DashboardMetrics = {
  total_claims: number
  at_risk: number
  denied: number
  needs_review: number
  claims_needing_attention: ClaimNeedingAttention[]
}

export async function fetchDashboard() {
  const res = await fetch(`${BASE}/api/dashboard`)
  if (!res.ok) throw new Error('Failed to fetch dashboard metrics')
  return (await res.json()) as DashboardMetrics
}
