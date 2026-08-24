import { useEffect, useState } from 'react'

export function Dashboard() {
  const [metrics, setMetrics] = useState<Record<string, any> | null>(null)

  useEffect(() => {
    fetch('/api/dashboard')
      .then((r) => r.json())
      .then(setMetrics)
      .catch(() => setMetrics(null))
  }, [])

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Overview</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Dashboard</h1>
      </div>

      {!metrics ? (
        <div className="rounded-2xl border border-slate-200 bg-slate-50 p-8 text-slate-600 shadow-sm">Loading…</div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-4 gap-4">
            <div className="rounded-lg bg-white p-4 shadow"> <div className="text-2xl font-bold">{metrics.total_claims}</div><div className="text-sm text-slate-500">Total Claims</div></div>
            <div className="rounded-lg bg-white p-4 shadow"> <div className="text-2xl font-bold">{metrics.at_risk}</div><div className="text-sm text-slate-500">At Risk</div></div>
            <div className="rounded-lg bg-white p-4 shadow"> <div className="text-2xl font-bold">{metrics.denied}</div><div className="text-sm text-slate-500">Denied</div></div>
            <div className="rounded-lg bg-white p-4 shadow"> <div className="text-2xl font-bold">{metrics.needs_review}</div><div className="text-sm text-slate-500">Awaiting Review</div></div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 text-slate-700 shadow-sm">
            <h2 className="text-lg font-medium mb-2">Claims Needing Attention</h2>
            <table className="w-full table-auto">
              <thead>
                <tr>
                  <th className="text-left p-2 text-sm text-slate-500">Claim ID</th>
                  <th className="text-left p-2 text-sm text-slate-500">Patient</th>
                  <th className="text-left p-2 text-sm text-slate-500">Amount</th>
                  <th className="text-left p-2 text-sm text-slate-500">Risk Score</th>
                </tr>
              </thead>
              <tbody>
                {metrics.claims_needing_attention.map((c: any) => (
                  <tr key={c.claim_id}>
                    <td className="p-2 text-sm text-slate-700">{c.claim_id}</td>
                    <td className="p-2 text-sm text-slate-700">{c.patient_name ?? ''}</td>
                    <td className="p-2 text-sm text-slate-700">${Number(c.amount).toFixed(2)}</td>
                    <td className="p-2 text-sm text-slate-700">{c.risk_score}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
