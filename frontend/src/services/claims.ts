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
