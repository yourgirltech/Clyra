import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchDashboard } from '../services/dashboard'
import type { DashboardMetrics } from '../services/dashboard'
import { StatCard } from '../components/ui/StatCard'

function humanize(key: string) {
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function riskScoreClass(score: number) {
  if (score >= 70) return 'text-red-600'
  if (score >= 40) return 'text-amber-500'
  return 'text-emerald-600'
}

export function Dashboard() {
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null)
  const [error, setError] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    fetchDashboard()
      .then(setMetrics)
      .catch(() => setError(true))
  }, [])

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">Portfolio health across every claim in the pipeline.</p>
      </div>

      {error ? (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-sm text-red-700 shadow-sm">
          Couldn't load dashboard metrics. Is the API running?
        </div>
      ) : !metrics ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[104px] animate-pulse rounded-2xl border border-slate-200 bg-slate-100" />
          ))}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Claims" value={metrics.total_claims} caption="Total Claims" tone="slate" />
            <StatCard label="At Risk" value={metrics.at_risk} caption="Needs Attention" tone="amber" />
            <StatCard label="Denied" value={metrics.denied} caption="This Month" tone="red" />
            <StatCard label="Awaiting Review" value={metrics.needs_review} caption="Pending" tone="blue" />
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
              <h2 className="text-base font-semibold text-slate-900">Claims Needing Attention</h2>
              <button
                onClick={() => navigate('/claims')}
                className="text-sm font-medium text-blue-600 hover:text-blue-700"
              >
                View all claims
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] table-auto">
                <thead>
                  <tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-400">
                    <th className="px-6 py-3">Claim ID</th>
                    <th className="px-6 py-3">Patient</th>
                    <th className="px-6 py-3">Payer</th>
                    <th className="px-6 py-3">Amount</th>
                    <th className="px-6 py-3">Risk Score</th>
                    <th className="px-6 py-3">Issue</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {metrics.claims_needing_attention.map((c) => (
                    <tr
                      key={c.claim_id}
                      onClick={() => navigate(`/claims/${c.claim_id}`)}
                      className="cursor-pointer transition hover:bg-slate-50"
                    >
                      <td className="px-6 py-3 text-sm font-medium text-slate-900">{c.claim_id}</td>
                      <td className="px-6 py-3 text-sm text-slate-600">{c.patient_name ?? '—'}</td>
                      <td className="px-6 py-3 text-sm text-slate-600">{c.payer_name ?? '—'}</td>
                      <td className="px-6 py-3 text-sm text-slate-600">${Number(c.amount).toFixed(2)}</td>
                      <td className={`px-6 py-3 text-sm font-semibold ${riskScoreClass(c.risk_score)}`}>
                        {c.risk_score}%
                      </td>
                      <td className="px-6 py-3 text-sm text-slate-600">
                        {c.primary_issue_type ? humanize(c.primary_issue_type) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
