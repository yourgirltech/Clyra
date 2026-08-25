import type { ReactNode } from 'react'

type Tone = 'slate' | 'blue' | 'indigo' | 'amber' | 'red' | 'emerald' | 'violet'

const toneClasses: Record<Tone, string> = {
  slate: 'bg-slate-100 text-slate-700 ring-1 ring-inset ring-slate-200',
  blue: 'bg-blue-50 text-blue-700 ring-1 ring-inset ring-blue-200',
  indigo: 'bg-indigo-50 text-indigo-700 ring-1 ring-inset ring-indigo-200',
  amber: 'bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200',
  red: 'bg-red-50 text-red-700 ring-1 ring-inset ring-red-200',
  emerald: 'bg-emerald-50 text-emerald-700 ring-1 ring-inset ring-emerald-200',
  violet: 'bg-violet-50 text-violet-700 ring-1 ring-inset ring-violet-200',
}

const dotClasses: Record<Tone, string> = {
  slate: 'bg-slate-400',
  blue: 'bg-blue-500',
  indigo: 'bg-indigo-500',
  amber: 'bg-amber-500',
  red: 'bg-red-500',
  emerald: 'bg-emerald-500',
  violet: 'bg-violet-500',
}

export function Badge({ tone, children, dot = false }: { tone: Tone; children: ReactNode; dot?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${toneClasses[tone]}`}
    >
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${dotClasses[tone]}`} />}
      {children}
    </span>
  )
}

const STATUS_TONE: Record<string, Tone> = {
  Draft: 'slate',
  Submitted: 'blue',
  Processing: 'indigo',
  'At Risk': 'amber',
  Denied: 'red',
  Paid: 'emerald',
  'Needs Review': 'violet',
}

const RISK_TONE: Record<string, Tone> = {
  Low: 'emerald',
  Medium: 'amber',
  High: 'red',
}

const SEVERITY_TONE: Record<string, Tone> = {
  low: 'emerald',
  medium: 'amber',
  high: 'red',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge tone={STATUS_TONE[status] ?? 'slate'} dot>
      {status}
    </Badge>
  )
}

export function RiskBadge({ level }: { level: string }) {
  return <Badge tone={RISK_TONE[level] ?? 'slate'}>{level}</Badge>
}

export function SeverityBadge({ severity }: { severity: string }) {
  return <Badge tone={SEVERITY_TONE[severity.toLowerCase()] ?? 'slate'}>{severity}</Badge>
}
