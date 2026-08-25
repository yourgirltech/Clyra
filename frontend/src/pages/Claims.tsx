import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronDown, Search } from 'lucide-react'
import { fetchClaims } from '../services/claims'
import type { Claim } from '../services/claims'
import ClaimsTable from '../components/ClaimsTable'
import type { SortingState } from '@tanstack/react-table'

const selectClass =
  'w-full appearance-none rounded-xl border border-slate-200 bg-white py-2 pl-3 pr-8 text-sm text-slate-700 transition focus:border-indigo-400 focus:outline-none focus:ring-2 focus:ring-indigo-100'

export function Claims() {
  const [claims, setClaims] = useState<Claim[]>([])
  const [loading, setLoading] = useState(false)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState<string | undefined>()
  const [risk, setRisk] = useState<string | undefined>()
  const [payer, setPayer] = useState<number | undefined>()
  

  const navigate = useNavigate()

  const [pageIndex, setPageIndex] = useState(0)
  const [pageSize] = useState(25)
  const [total, setTotal] = useState(0)
  const [sorting, setSorting] = useState<SortingState>([])

  useEffect(() => {
    setLoading(true)
    const sort_by = sorting[0]?.id
    const sort_dir = sorting[0]?.desc ? 'desc' : 'asc'
    fetchClaims({ search, status, risk_level: risk, payer_id: payer, page: pageIndex + 1, size: pageSize, sort_by, sort_dir })
      .then((data) => {
        setClaims(data.items)
        setTotal(data.total)
      })
      .finally(() => setLoading(false))
  }, [search, status, risk, payer, pageIndex, pageSize])

  const payerOptions = useMemo(() => {
    const map = new Map<number, string>()
    claims.forEach((c) => {
      if (c.payer_id && c.payer_name) map.set(c.payer_id, c.payer_name)
    })
    return Array.from(map.entries())
  }, [claims])

  // Use a local TanStack-powered table component (typed)

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Operations</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">Claims</h1>
        <p className="mt-1 text-sm text-slate-500">Search, filter, and triage every claim in the pipeline.</p>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex min-w-[220px] flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
          <Search className="h-4 w-4 shrink-0 text-slate-400" />
          <input
            placeholder="Search claim id"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
          />
        </div>
        <div className="relative">
          <select value={status ?? ''} onChange={(e) => setStatus(e.target.value || undefined)} className={selectClass}>
            <option value="">All Statuses</option>
            <option>Draft</option>
            <option>Submitted</option>
            <option>Processing</option>
            <option>At Risk</option>
            <option>Denied</option>
            <option>Paid</option>
            <option>Needs Review</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>
        <div className="relative">
          <select value={risk ?? ''} onChange={(e) => setRisk(e.target.value || undefined)} className={selectClass}>
            <option value="">All Risk</option>
            <option>Low</option>
            <option>Medium</option>
            <option>High</option>
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>
        <div className="relative">
          <select
            value={payer ?? ''}
            onChange={(e) => setPayer(e.target.value ? Number(e.target.value) : undefined)}
            className={selectClass}
          >
            <option value="">All Payers</option>
            {payerOptions.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4 text-slate-700 shadow-sm">
        {loading ? (
          <div className="p-8 text-center text-sm text-slate-500">Loading…</div>
        ) : (
          <ClaimsTable
            items={claims}
            pageIndex={pageIndex}
            pageSize={pageSize}
            total={total}
            onPageChange={(p) => setPageIndex(p)}
            onRowClick={(r) => navigate(`/claims/${r.claim_id}`)}
            sorting={sorting}
            onSortingChange={(s) => { setSorting(s); setPageIndex(0); }}
          />
        )}
      </div>
    </div>
  )
}
