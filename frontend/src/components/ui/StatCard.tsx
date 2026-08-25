type Tone = 'slate' | 'amber' | 'red' | 'blue'
type ReactValue = string | number

const valueToneClasses: Record<Tone, string> = {
  slate: 'text-slate-900',
  amber: 'text-amber-500',
  red: 'text-red-600',
  blue: 'text-blue-600',
}

const captionToneClasses: Record<Tone, string> = {
  slate: 'text-slate-400',
  amber: 'text-slate-400',
  red: 'text-slate-400',
  blue: 'text-blue-600',
}

export function StatCard({
  label,
  value,
  caption,
  tone,
}: {
  label: string
  value: ReactValue
  caption: string
  tone: Tone
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-slate-300">
      <p className="text-sm font-medium text-slate-700">{label}</p>
      <p className={`mt-2 text-3xl font-bold tracking-tight ${valueToneClasses[tone]}`}>{value}</p>
      <p className={`mt-2 text-sm ${captionToneClasses[tone]}`}>{caption}</p>
    </div>
  )
}
