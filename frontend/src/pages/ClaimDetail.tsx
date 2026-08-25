import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, ChevronDown, Sparkles } from 'lucide-react'
import { fetchClaim, fetchClaimAnalysis } from '../services/claims'
import type { Claim } from '../services/claims'
import { RiskBadge, SeverityBadge, StatusBadge } from '../components/ui/Badge'

function humanize(key: string) {
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function ClaimDetail() {
  const { claimId } = useParams()
  const [claim, setClaim] = useState<Claim | null>(null)
  const [analysis, setAnalysis] = useState<any | null>(null)

  useEffect(() => {
    if (!claimId) return
    fetchClaim(claimId).then(setClaim).catch(() => setClaim(null))
    fetchClaimAnalysis(claimId).then(setAnalysis).catch(() => setAnalysis(null))
  }, [claimId])

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Claim Review</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Claim Detail</h1>
      </div>

      {!claim ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-8 text-sm text-slate-500 shadow-sm">Loading…</div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Claim ID</p>
                <p className="mt-1 text-xl font-semibold text-slate-900">{claim.claim_id}</p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge status={claim.status} />
                <RiskBadge level={claim.risk_level} />
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 gap-6 border-t border-slate-100 pt-6 sm:grid-cols-4">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Patient</p>
                <p className="mt-1 text-sm font-medium text-slate-800">{claim.patient_name ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Payer</p>
                <p className="mt-1 text-sm font-medium text-slate-800">{claim.payer_name ?? '—'}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Amount</p>
                <p className="mt-1 text-sm font-medium text-slate-800">${Number(claim.amount).toFixed(2)}</p>
              </div>
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Risk Score</p>
                <p className="mt-1 text-sm font-medium text-slate-800">{claim.risk_score}%</p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">What Clyra found</h2>

            {!analysis ? (
              <p className="mt-3 text-sm text-slate-500">Analyzing…</p>
            ) : analysis.issues && analysis.issues.length ? (
              <div className="mt-4 space-y-3">
                {analysis.issues.map((iss: any, idx: number) => (
                  <details key={idx} className="group rounded-xl border border-slate-200 bg-slate-50 p-4 open:bg-white">
                    <summary className="flex cursor-pointer list-none items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                        <div>
                          <p className="text-sm font-semibold text-slate-900">{humanize(iss.issue_type)}</p>
                          <p className="mt-0.5 text-sm text-slate-600">{iss.description}</p>
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <SeverityBadge severity={iss.severity} />
                        <ChevronDown className="h-4 w-4 text-slate-400 transition group-open:rotate-180" />
                      </div>
                    </summary>
                    <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                      {JSON.stringify(iss.evidence, null, 2)}
                    </pre>
                  </details>
                ))}
              </div>
            ) : (
              <div className="mt-4 flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-700">
                <CheckCircle2 className="h-4 w-4" />
                No issues detected.
              </div>
            )}
          </div>

          <div className="flex items-start gap-3 rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 p-5">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
            <div>
              <p className="text-sm font-semibold text-indigo-900">Recommended next step</p>
              <p className="mt-0.5 text-sm text-indigo-700/80">
                Coming soon — the AI recommendation layer will suggest an action here, subject to your approval.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
