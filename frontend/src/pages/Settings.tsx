import { Bell, Building2, Lock, ShieldCheck, UserCircle } from 'lucide-react'

function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Bell
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          <p className="mt-0.5 text-sm text-slate-500">{description}</p>
        </div>
      </div>
      <div className="mt-5 space-y-4 border-t border-slate-100 pt-5">{children}</div>
    </div>
  )
}

function FieldRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium text-slate-700">{label}</p>
        {hint && <p className="text-xs text-slate-400">{hint}</p>}
      </div>
      <input
        readOnly
        value={value}
        className="w-56 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-600"
      />
    </div>
  )
}

function ToggleRow({ label, hint, checked }: { label: string; hint?: string; checked: boolean }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium text-slate-700">{label}</p>
        {hint && <p className="text-xs text-slate-400">{hint}</p>}
      </div>
      <div
        className={`flex h-6 w-11 shrink-0 items-center rounded-full px-0.5 ${
          checked ? 'justify-end bg-indigo-500' : 'justify-start bg-slate-200'
        }`}
      >
        <div className="h-5 w-5 rounded-full bg-white shadow" />
      </div>
    </div>
  )
}

export function Settings() {
  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Configuration</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900">Settings</h1>
          <p className="mt-1 text-sm text-slate-500">Workspace, approval, and notification preferences.</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
          <Lock className="h-3.5 w-3.5" />
          Read-only preview
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <SettingsSection icon={Building2} title="Workspace" description="Clinic identity and demo environment details.">
          <FieldRow label="Workspace name" value="Clyra Demo Clinic" />
          <FieldRow label="Environment" value="Development" hint="Set via backend .env" />
          <FieldRow label="Data mode" value="Synthetic only" hint="No real PHI is used in this environment" />
        </SettingsSection>

        <SettingsSection icon={UserCircle} title="Account" description="Signed-in user for this session.">
          <FieldRow label="Name" value="A. Carter" />
          <FieldRow label="Role" value="Claims Reviewer" />
        </SettingsSection>

        <SettingsSection
          icon={ShieldCheck}
          title="Approval controls"
          description="Guardrails around AI recommendations — matches docs/ai-design.md."
        >
          <ToggleRow
            label="Require human approval for all actions"
            hint="Cannot be disabled — AI recommends, humans decide"
            checked
          />
          <ToggleRow
            label="Auto-escalate low-confidence recommendations"
            hint="Routes to 06-escalation-agent instead of one-click approval"
            checked
          />
        </SettingsSection>

        <SettingsSection icon={Bell} title="Notifications" description="Alerts for claims needing attention.">
          <ToggleRow label="Email me when a claim is escalated" checked={false} />
          <ToggleRow label="Daily digest of At Risk claims" checked />
        </SettingsSection>
      </div>

      <div className="mt-5 rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 p-5 text-sm text-indigo-700/80">
        This page is a visual preview — controls are not yet wired to the backend. Editable settings land once the
        Commander agent pipeline (Phase 4) is in place.
      </div>
    </div>
  )
}
