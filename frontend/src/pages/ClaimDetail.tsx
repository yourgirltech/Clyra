import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchClaim, fetchClaimAnalysis, Claim } from '../services/claims'

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

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-8 text-slate-600 shadow-sm">
        {!claim ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <div>
            <h2 className="text-lg font-medium text-slate-800">What Clyra found</h2>
            {!analysis ? (
              <p className="text-sm text-slate-500">Analyzing…</p>
            ) : (
              <div className="mt-3 space-y-4">
                {analysis.issues && analysis.issues.length ? (
                  analysis.issues.map((iss: any, idx: number) => (
                    <div key={idx} className="rounded-md border p-3 bg-white">
                      <div className="flex items-center justify-between">
                        <div className="text-sm font-semibold text-slate-900">{iss.issue_type}</div>
                        <div className="text-xs text-slate-600">Severity: {iss.severity}</div>
                      </div>
                      <div className="text-sm text-slate-700 mt-1">Why: {iss.description}</div>
                      <details className="mt-2 text-xs text-slate-600">
                        <summary className="cursor-pointer">Evidence</summary>
                        <pre className="whitespace-pre-wrap">{JSON.stringify(iss.evidence, null, 2)}</pre>
                      </details>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">No issues detected.</p>
                )}

                <div className="pt-2 text-sm">
                  <div className="font-medium">Risk:</div>
                  <div className="text-slate-700">Level: {analysis.risk_level} — Score: {analysis.risk_score}</div>
                </div>
              </div>
            )}
            <div className="mt-6 text-sm text-slate-500">
              <div className="font-medium">Recommended next step</div>
              <div>Placeholder for recommended action (AI in later phase)</div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
