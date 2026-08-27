import { useCallback, useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { AlertCircle, CheckCircle2, ChevronDown, Clock, Sparkles, ThumbsDown, ThumbsUp } from 'lucide-react'
import {
  approveRecommendation,
  declineRecommendation,
  fetchClaim,
  fetchClaimActivity,
  fetchClaimAnalysis,
  fetchLatestRecommendation,
  generateRecommendation,
} from '../services/claims'
import type { ActivityLogEntry, Recommendation, RecommendationActionResult } from '../services/claims'
import type { Claim } from '../services/claims'
import { Badge, RiskBadge, SeverityBadge, StatusBadge } from '../components/ui/Badge'

function humanize(key: string) {
  return key
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

function describeDecisionOutcome(approve: boolean, result: RecommendationActionResult): string {
  if (!approve) {
    return 'Declined — recorded, no automated action will run.'
  }

  const execution = result.execution
  if (execution) {
    if (execution.kind === 'FollowUpResult') {
      const due = execution.due_at ? new Date(execution.due_at).toLocaleDateString() : 'no due date'
      return `Approved — follow-up created (FollowUp #${execution.followup_id}, due ${due}).`
    }
    if (execution.kind === 'ReminderResult') {
      return `Approved — reminder sent to ${execution.target} (Reminder #${execution.reminder_id}).`
    }
    // FollowUpFailure | ReminderFailure — the executor agent tried and failed.
    const failedNote = `attempted, then failed (${execution.reason.replaceAll('_', ' ')}) after ${execution.attempts} attempt(s)`
    if (result.escalation_id != null) {
      return `Approved — execution ${failedNote}, escalated for review. Escalation #${result.escalation_id}.`
    }
    return `Approved — execution ${failedNote}.`
  }

  if (result.decision.decision === '06-escalation-agent') {
    return `Approved — escalated for review (${result.decision.reason_code}, rule ${result.decision.rule}). Escalation #${result.escalation_id}.`
  }
  return `Approved — ${result.decision.reason_code.replaceAll('_', ' ')}.`
}

const CONFIDENCE_TONE = { High: 'emerald', Medium: 'amber', Low: 'red' } as const

function ConfidenceBadge({ confidence }: { confidence: string | null }) {
  if (!confidence) return null
  const tone = CONFIDENCE_TONE[confidence as keyof typeof CONFIDENCE_TONE] ?? 'slate'
  return <Badge tone={tone}>{confidence} confidence</Badge>
}

function formatTimestamp(value: string) {
  return new Date(value).toLocaleString()
}

// Activity log entries come from two different writers with different detail
// shapes: pipeline.py's approve/decline entries carry a Commander decision
// (commander_decision/reason_code/rule); 04/05's own entries — written
// directly by app.agents.followup/reminder, never through Commander —
// describe the execution attempt instead (followup_id/attempts/reason).
function describeActivityDetails(item: ActivityLogEntry): string | null {
  const d = item.details
  if (!d) return null

  if ('commander_decision' in d) {
    const parts = [`Commander → ${d.commander_decision} (${d.reason_code}, rule ${d.rule})`]
    if (d.action_type) parts.unshift(`action: ${d.action_type}`)
    if (d.escalation_id != null) parts.push(`escalation #${d.escalation_id}`)
    return parts.join(' · ')
  }

  if (item.action === 'followup_completed' || item.action === 'reminder_completed') {
    const id = d.followup_id ?? d.reminder_id
    const attempts = d.attempts === 1 ? '1 attempt' : `${d.attempts} attempts`
    return `record #${id} · ${attempts} · approved by ${d.approver}`
  }

  if (item.action === 'followup_failed' || item.action === 'reminder_failed') {
    return `${d.reason?.replaceAll('_', ' ')} — ${d.detail} (${d.attempts} attempt(s))`
  }

  return null
}

function ActivityTimeline({ items }: { items: ActivityLogEntry[] }) {
  if (!items.length) {
    return <p className="mt-3 text-sm text-slate-500">No activity recorded yet.</p>
  }
  return (
    <ol className="mt-4 space-y-4">
      {items.map((item) => {
        const detail = describeActivityDetails(item)
        return (
        <li key={item.id} className="flex gap-3">
          <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-500">
            <Clock className="h-3.5 w-3.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-medium text-slate-900">{humanize(item.action)}</p>
              <span className="text-xs text-slate-400">{formatTimestamp(item.created_at)}</span>
            </div>
            {detail && <p className="mt-0.5 text-xs text-slate-500">{detail}</p>}
          </div>
        </li>
        )
      })}
    </ol>
  )
}

export function ClaimDetail() {
  const { claimId } = useParams()
  const [claim, setClaim] = useState<Claim | null>(null)
  const [analysis, setAnalysis] = useState<any | null>(null)
  const [recommendation, setRecommendation] = useState<Recommendation | null | undefined>(undefined)
  const [activity, setActivity] = useState<ActivityLogEntry[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadRecommendation = useCallback((id: string) => {
    fetchLatestRecommendation(id)
      .then(setRecommendation)
      .catch(() => setRecommendation(null))
  }, [])

  const loadActivity = useCallback((id: string) => {
    fetchClaimActivity(id)
      .then(setActivity)
      .catch(() => setActivity([]))
  }, [])

  useEffect(() => {
    if (!claimId) return
    fetchClaim(claimId).then(setClaim).catch(() => setClaim(null))
    fetchClaimAnalysis(claimId).then(setAnalysis).catch(() => setAnalysis(null))
    loadRecommendation(claimId)
    loadActivity(claimId)
  }, [claimId, loadRecommendation, loadActivity])

  async function handleGenerate() {
    if (!claimId) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const result = await generateRecommendation(claimId)
      if (result.stage === 'no_action') {
        setNotice(`Commander took no action (${result.detail.replaceAll('_', ' ')}).`)
      }
      // Only overwrite what's displayed when a new recommendation actually
      // came back — a "no_action" result (e.g. a terminal claim) returns
      // null even when a still-valid resolved recommendation exists, and
      // that shouldn't erase it from view.
      if (result.recommendation) {
        setRecommendation(result.recommendation)
      }
      if (result.stage === 'escalated' && !result.recommendation) {
        setNotice('Escalated to human review — see the escalation record.')
      }
      loadActivity(claimId)
      fetchClaim(claimId).then(setClaim).catch(() => {})
    } catch (e: any) {
      setError(e.message ?? 'Failed to generate recommendation')
    } finally {
      setBusy(false)
    }
  }

  async function handleDecision(approve: boolean) {
    if (!claimId || !recommendation) return
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const fn = approve ? approveRecommendation : declineRecommendation
      const result = await fn(claimId, recommendation.id)
      setRecommendation(result.recommendation)
      setNotice(describeDecisionOutcome(approve, result))
      loadActivity(claimId)
    } catch (e: any) {
      setError(e.message ?? 'Failed to record decision')
    } finally {
      setBusy(false)
    }
  }

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

          <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-5">
            <div className="flex items-start gap-3">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-indigo-900">Recommended next step</p>

                {recommendation === undefined && <p className="mt-1 text-sm text-indigo-700/80">Loading…</p>}

                {recommendation === null && (
                  <div className="mt-2">
                    <p className="text-sm text-indigo-700/80">
                      No recommendation yet. Run Clyra's analyzer → reasoning → recommendation pipeline for this claim.
                    </p>
                    <button
                      onClick={handleGenerate}
                      disabled={busy}
                      className="mt-3 inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {busy ? 'Running…' : 'Analyze & Recommend'}
                    </button>
                  </div>
                )}

                {recommendation && (
                  <div className="mt-2 space-y-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="violet">{recommendation.action_type ? humanize(recommendation.action_type) : '—'}</Badge>
                      <ConfidenceBadge confidence={recommendation.confidence} />
                      <Badge
                        tone={
                          recommendation.approval_status === 'pending'
                            ? 'blue'
                            : recommendation.approval_status === 'approved'
                              ? 'emerald'
                              : recommendation.approval_status === 'declined'
                                ? 'slate'
                                : 'red'
                        }
                      >
                        {humanize(recommendation.approval_status)}
                      </Badge>
                    </div>

                    <p className="text-sm text-indigo-900/90">{recommendation.rationale}</p>

                    {recommendation.cited_issue_types.length > 0 && (
                      <div className="flex flex-wrap gap-1.5">
                        {recommendation.cited_issue_types.map((t) => (
                          <Badge key={t} tone="slate">
                            {humanize(t)}
                          </Badge>
                        ))}
                      </div>
                    )}

                    {recommendation.approval_status === 'pending' && (
                      <div className="flex gap-2 pt-1">
                        <button
                          onClick={() => handleDecision(true)}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white shadow-sm transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <ThumbsUp className="h-3.5 w-3.5" />
                          Approve
                        </button>
                        <button
                          onClick={() => handleDecision(false)}
                          disabled={busy}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          <ThumbsDown className="h-3.5 w-3.5" />
                          Decline
                        </button>
                      </div>
                    )}

                    {recommendation.approval_status === 'escalated' && (
                      <p className="text-xs text-red-700">
                        Confidence too low for a one-click approval — escalated to human review automatically.
                      </p>
                    )}

                    {recommendation.approval_status !== 'pending' && (
                      <div className="pt-1">
                        <button
                          onClick={handleGenerate}
                          disabled={busy}
                          className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-sm font-medium text-indigo-700 shadow-sm transition hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {busy ? 'Running…' : 'Re-analyze & Recommend'}
                        </button>
                      </div>
                    )}
                  </div>
                )}

                {notice && <p className="mt-3 text-sm font-medium text-indigo-800">{notice}</p>}
                {error && <p className="mt-3 text-sm font-medium text-red-700">{error}</p>}
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="text-base font-semibold text-slate-900">Activity</h2>
            <ActivityTimeline items={activity} />
          </div>
        </div>
      )}
    </div>
  )
}
