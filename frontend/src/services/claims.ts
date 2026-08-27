export type Claim = {
  id: number
  claim_id: string
  clinic_id: number
  payer_id: number
  payer_name?: string
  patient_id?: number
  patient_name?: string
  amount: number
  status: string
  risk_level: string
  risk_score: number
  created_at: string
  updated_at?: string
}

const BASE = (import.meta as any).env?.VITE_API_BASE ?? 'http://127.0.0.1:8000'

export type ClaimListResponse = {
  items: Claim[]
  total: number
  page: number
  size: number
}

export async function fetchClaims(params: Record<string, string | number | undefined> = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) query.set(k, String(v))
  })
  const url = `${BASE}/api/claims?${query.toString()}`
  const res = await fetch(url)
  if (!res.ok) throw new Error('Failed to fetch claims')
  return (await res.json()) as ClaimListResponse
}

export async function fetchClaim(id: string) {
  const res = await fetch(`${BASE}/api/claims/${encodeURIComponent(id)}`)
  if (!res.ok) throw new Error('Failed to fetch claim')
  return (await res.json()) as Claim
}

export type Issue = {
  issue_type: string
  severity: string
  description: string
  evidence: Record<string, any>
}

export type ClaimAnalysis = {
  issues: Issue[]
  risk_score: number
  risk_level: string
}

export async function fetchClaimAnalysis(id: string) {
  const res = await fetch(`${BASE}/api/claims/${encodeURIComponent(id)}/analyze`)
  if (!res.ok) throw new Error('Failed to fetch analysis')
  return (await res.json()) as ClaimAnalysis
}

export type ApprovalStatus = 'pending' | 'approved' | 'declined' | 'escalated'

export type Recommendation = {
  id: number
  claim_id: number
  action_type: string | null
  rationale: string
  confidence: string | null
  low_confidence: boolean
  cited_issue_types: string[]
  secondary_options: { action_type: string; rationale: string; confidence: string }[]
  approval_status: ApprovalStatus
  created_at: string
  decided_at?: string | null
}

export type CommanderDecisionOut = {
  decision: string
  reason_code: string
  rule: number
}

export type ExecutionResult =
  | { kind: 'FollowUpResult'; claim_id: string; followup_id: number; note: string; due_at: string | null; attempts: number; activity_log_id: number }
  | { kind: 'FollowUpFailure'; claim_id: string | null; reason: string; detail: string; attempts: number; activity_log_id: number | null }
  | { kind: 'ReminderResult'; claim_id: string; reminder_id: number; target: string; content: string; reference_number: string | null; attempts: number; activity_log_id: number }
  | { kind: 'ReminderFailure'; claim_id: string | null; reason: string; detail: string; attempts: number; activity_log_id: number | null }

export type RecommendationActionResult = {
  recommendation: Recommendation
  decision: CommanderDecisionOut
  execution: ExecutionResult | null
  execution_decision: CommanderDecisionOut | null
  escalation_id: number | null
  activity?: ActivityLogEntry
}

export type GenerateRecommendationResult = {
  stage: 'pending' | 'escalated' | 'no_action'
  detail: string
  decision: CommanderDecisionOut | null
  recommendation: Recommendation | null
  escalation_id: number | null
}

export type ActivityLogEntry = {
  id: number
  action: string
  details: Record<string, any> | null
  created_at: string
}

async function asJson<T>(res: Response, errorMessage: string): Promise<T> {
  if (!res.ok) {
    let detail = errorMessage
    try {
      const body = await res.json()
      if (body?.detail) detail = body.detail
    } catch {
      // ignore — fall back to the generic message
    }
    throw new Error(detail)
  }
  return (await res.json()) as T
}

export async function fetchLatestRecommendation(claimId: string) {
  const res = await fetch(`${BASE}/api/claims/${encodeURIComponent(claimId)}/recommendation`)
  const body = await asJson<{ recommendation: Recommendation | null }>(res, 'Failed to fetch recommendation')
  return body.recommendation
}

export async function generateRecommendation(claimId: string) {
  const res = await fetch(`${BASE}/api/claims/${encodeURIComponent(claimId)}/recommendation`, { method: 'POST' })
  return asJson<GenerateRecommendationResult>(res, 'Failed to generate recommendation')
}

export async function approveRecommendation(claimId: string, recommendationId: number) {
  const res = await fetch(
    `${BASE}/api/claims/${encodeURIComponent(claimId)}/recommendation/${recommendationId}/approve`,
    { method: 'POST' },
  )
  return asJson<RecommendationActionResult>(res, 'Failed to approve recommendation')
}

export async function declineRecommendation(claimId: string, recommendationId: number) {
  const res = await fetch(
    `${BASE}/api/claims/${encodeURIComponent(claimId)}/recommendation/${recommendationId}/decline`,
    { method: 'POST' },
  )
  return asJson<RecommendationActionResult>(res, 'Failed to decline recommendation')
}

export async function fetchClaimActivity(claimId: string) {
  const res = await fetch(`${BASE}/api/claims/${encodeURIComponent(claimId)}/activity`)
  const body = await asJson<{ items: ActivityLogEntry[] }>(res, 'Failed to fetch activity')
  return body.items
}
