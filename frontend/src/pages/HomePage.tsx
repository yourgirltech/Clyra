import { Link } from 'react-router-dom'
import {
  AlertCircle,
  ArrowRight,
  Bot,
  CheckCircle2,
  ClipboardCheck,
  FileText,
  PlayCircle,
  Plus,
  ShieldCheck,
  Sparkles,
  UserCheck,
  Zap,
} from 'lucide-react'
import { RiskBadge, SeverityBadge } from '../components/ui/Badge'

const navLinks = ['Product', 'How It Works', 'Use Cases', 'Pricing', 'Resources']

const processSteps = [
  {
    icon: FileText,
    title: 'Claim Submitted',
    description: 'A new claim enters the pipeline with its evidence and payer requirements.',
    accent: 'from-blue-500 to-cyan-400',
  },
  {
    icon: Bot,
    title: 'AI Analyzes',
    description: 'The deterministic rule engine scores risk and surfaces issues automatically.',
    accent: 'from-indigo-500 to-blue-400',
  },
  {
    icon: AlertCircle,
    title: 'Issue Identified',
    description: 'Missing authorization, documentation gaps, or coding mismatches are flagged.',
    accent: 'from-amber-500 to-orange-400',
  },
  {
    icon: UserCheck,
    title: 'Human Review',
    description: 'A reviewer sees the evidence and decides — no action happens without approval.',
    accent: 'from-violet-500 to-purple-400',
  },
  {
    icon: Zap,
    title: 'Automation Executes',
    description: 'Once approved, the agent-routed automation layer carries out the action.',
    accent: 'from-fuchsia-500 to-pink-400',
  },
  {
    icon: CheckCircle2,
    title: 'Resolution & Recovery',
    description: 'The claim moves toward payment, with a full audit trail of every step.',
    accent: 'from-emerald-500 to-teal-400',
  },
]

const demoClaim = {
  claimId: 'CL-10002',
  patient: 'Logan Martin',
  payer: 'DistPayerHigh',
  amount: 3826.33,
  riskLevel: 'High',
  riskScore: 100,
  issues: [
    { issue_type: 'Missing Authorization', severity: 'high', description: 'Authorization required by payer but missing on claim.' },
    { issue_type: 'Missing Documentation', severity: 'medium', description: 'Required documentation not found for this claim.' },
    { issue_type: 'Code Mismatch', severity: 'medium', description: 'Claim coding does not match expected payer coding rules.' },
    { issue_type: 'Overdue Follow-Up', severity: 'medium', description: 'Follow-up overdue by payer policy (30 days).' },
  ],
}

const features = [
  {
    icon: ShieldCheck,
    number: '01',
    title: 'Deterministic risk scoring',
    description:
      'Every claim is scored by a transparent rule engine first — issues, severity, and risk level are computed the same way every time, before any AI touches the claim.',
    accent: 'from-blue-500 to-cyan-400',
    glow: 'bg-blue-500/10',
  },
  {
    icon: Sparkles,
    number: '02',
    title: 'Explainable AI reasoning',
    description:
      'AI agents explain what the rule engine found and propose next steps, always tracing back to the specific evidence that grounds each statement.',
    accent: 'from-indigo-500 to-purple-400',
    glow: 'bg-indigo-500/10',
  },
  {
    icon: UserCheck,
    number: '03',
    title: 'Human-approved actions',
    description:
      'AI recommends, your team decides. No follow-up, reminder, or status change ever executes without an explicit human approval.',
    accent: 'from-violet-500 to-fuchsia-400',
    glow: 'bg-violet-500/10',
  },
  {
    icon: ClipboardCheck,
    number: '04',
    title: 'Full audit trail',
    description:
      'Every recommendation, approval, and executed action is logged with the evidence behind it, so any decision can be traced and reviewed after the fact.',
    accent: 'from-emerald-500 to-teal-400',
    glow: 'bg-emerald-500/10',
  },
]

export function HomePage() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/20">
              <Plus className="h-5 w-5" strokeWidth={3} />
            </div>
            <p className="font-display text-lg font-bold text-slate-900">Clyra</p>
          </div>

          <nav className="hidden items-center gap-1 lg:flex">
            {navLinks.map((item) => (
              <a
                key={item}
                href={item === 'Product' ? '#how-it-works' : '#'}
                className="group relative px-3.5 py-2 text-sm font-semibold text-slate-600 transition hover:text-slate-900"
              >
                {item}
                <span className="absolute inset-x-3.5 -bottom-0.5 h-0.5 origin-left scale-x-0 rounded-full bg-gradient-to-r from-blue-500 to-cyan-400 transition-transform duration-200 ease-out group-hover:scale-x-100" />
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-5">
            <Link to="/dashboard" className="hidden text-sm font-medium text-slate-600 transition hover:text-slate-900 sm:block">
              Sign in
            </Link>
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600! px-4 py-2 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-500!"
            >
              Book a Demo
            </Link>
          </div>
        </div>
      </header>

      <section
        className="relative overflow-hidden bg-no-repeat"
        style={{
          backgroundImage: "url('/hero-visual.png')",
          backgroundSize: '100% auto',
          backgroundPosition: 'center top',
        }}
      >
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(115deg, rgba(255,255,255,0.98) 0%, rgba(255,255,255,0.94) 20%, rgba(255,255,255,0.7) 42%, rgba(255,255,255,0.25) 62%, rgba(255,255,255,0.05) 80%)',
          }}
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              'linear-gradient(0deg, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0) 35%)',
          }}
        />

        <div className="relative mx-auto max-w-7xl px-6 py-20 lg:py-28">
          <div className="max-w-xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.15em] text-blue-700">
              AI Health Insurance Claims Operations
            </span>
            <h1 className="mt-6 font-display text-4xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
              Clear, explainable health insurance claim risk —{' '}
              <span className="text-blue-600">decided by your team.</span>
            </h1>
            <p className="mt-5 max-w-lg text-lg font-medium text-slate-800">
              Clyra helps health insurance billing and revenue-cycle teams triage health insurance
              claims with deterministic risk scoring and AI-guided recommendations. Every
              consequential action still requires human approval.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-4">
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600! px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-500!"
              >
                Book a Demo
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white/70 px-6 py-3 text-sm font-semibold text-slate-700 backdrop-blur-sm transition hover:border-slate-400 hover:bg-white"
              >
                <PlayCircle className="h-4 w-4" />
                See How It Works
              </a>
            </div>
            <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/70 px-4 py-2 text-xs font-medium text-slate-500 backdrop-blur-sm">
              Demo environment — synthetic data only
            </div>
          </div>
        </div>
      </section>

      <section id="how-it-works" className="bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="mb-10 text-center">
            <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-indigo-600">
              Capabilities
            </p>
            <h2 className="mt-3 font-display text-2xl font-bold tracking-tight text-slate-900 md:text-4xl">
              Smarter Claims. <span className="text-indigo-600">Stronger Revenue.</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <div
                key={f.title}
                className="group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition duration-300 hover:-translate-y-1 hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/60"
              >
                <div
                  className={`pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full ${f.glow} blur-2xl transition-opacity duration-300 group-hover:opacity-100 opacity-70`}
                />
                <span className="absolute right-5 top-5 font-mono text-4xl font-bold text-slate-100 transition-colors duration-300 group-hover:text-slate-200">
                  {f.number}
                </span>

                <div className="relative">
                  <div
                    className={`flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br ${f.accent} text-white shadow-md`}
                  >
                    <f.icon className="h-5 w-5" strokeWidth={2.25} />
                  </div>
                  <h3 className="mt-5 font-display text-sm font-bold text-slate-900">{f.title}</h3>
                  <span className={`mt-2 block h-0.5 w-8 rounded-full bg-gradient-to-r ${f.accent}`} />
                  <p className="mt-3 text-sm leading-relaxed text-slate-500">{f.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="mb-14 text-center">
            <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-indigo-600">
              The Workflow
            </p>
            <h2 className="mt-3 font-display text-2xl font-bold tracking-tight text-slate-900 md:text-4xl">
              From Claim to <span className="text-indigo-600">Resolution</span> — Seamlessly
            </h2>
          </div>

          <div className="relative flex gap-6 overflow-x-auto pb-4 lg:gap-3 lg:overflow-visible">
            <div className="absolute inset-x-0 top-[27px] hidden h-px bg-gradient-to-r from-blue-200 via-violet-200 to-emerald-200 lg:block" />

            {processSteps.map((step, i) => (
              <div key={step.title} className="group relative w-40 shrink-0 lg:w-auto lg:flex-1">
                <div className="flex flex-col items-center text-center">
                  <div
                    className={`relative z-10 flex h-[54px] w-[54px] items-center justify-center rounded-full bg-gradient-to-br ${step.accent} text-white shadow-md shadow-slate-300/50 ring-4 ring-white transition-transform duration-300 group-hover:scale-110`}
                  >
                    <step.icon className="h-5 w-5" strokeWidth={2.25} />
                    <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-slate-900 font-mono text-[10px] font-bold text-white">
                      {i + 1}
                    </span>
                  </div>
                  <h3 className="mt-4 font-display text-sm font-bold text-slate-900">{step.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto max-w-4xl px-6 py-16">
          <div className="mb-10 text-center">
            <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-indigo-600">
              See It In Action
            </p>
            <h2 className="mt-3 font-display text-2xl font-bold tracking-tight text-slate-900 md:text-4xl">
              A real claim, analyzed by the <span className="text-indigo-600">real rule engine.</span>
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500">
              Pulled directly from our synthetic demo dataset — the same deterministic engine that powers
              every claim in the live dashboard.
            </p>
          </div>

          <div className="relative">
            <div className="absolute -inset-4 -z-10 rounded-[2rem] bg-gradient-to-br from-blue-200/40 via-indigo-100/40 to-transparent blur-2xl" />

            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl shadow-slate-200/60">
              <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-5 py-3">
                <div className="flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-full bg-red-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
                  <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
                  <span className="ml-3 font-mono text-xs text-slate-400">rule-engine · output</span>
                </div>
                <div className="flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200">
                  <span className="relative flex h-1.5 w-1.5">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                  </span>
                  Live
                </div>
              </div>

              <div className="p-6 md:p-8">
                <div className="flex flex-wrap items-center justify-between gap-6 border-b border-slate-100 pb-6">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Claim ID</p>
                    <p className="mt-1 font-display text-xl font-bold text-slate-900">{demoClaim.claimId}</p>
                    <p className="mt-0.5 text-sm text-slate-500">
                      {demoClaim.patient} · {demoClaim.payer} · ${demoClaim.amount.toFixed(2)}
                    </p>
                  </div>

                  <div className="flex items-center gap-4">
                    <RiskBadge level={demoClaim.riskLevel} />
                    <div
                      className="relative flex h-16 w-16 shrink-0 items-center justify-center rounded-full"
                      style={{
                        background: `conic-gradient(#dc2626 ${demoClaim.riskScore}%, #fee2e2 ${demoClaim.riskScore}% 100%)`,
                      }}
                    >
                      <div className="flex h-[52px] w-[52px] items-center justify-center rounded-full bg-white">
                        <span className="text-sm font-bold text-red-600">{demoClaim.riskScore}%</span>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="mt-6 space-y-2.5">
                  {demoClaim.issues.map((issue) => {
                    const sev = issue.severity as 'high' | 'medium' | 'low'
                    const styles = {
                      high: { border: 'border-l-red-400', icon: 'text-red-500' },
                      medium: { border: 'border-l-amber-400', icon: 'text-amber-500' },
                      low: { border: 'border-l-emerald-400', icon: 'text-emerald-500' },
                    }[sev]
                    return (
                      <div
                        key={issue.issue_type}
                        className={`flex items-start justify-between gap-3 rounded-r-xl rounded-l-md border border-slate-200 border-l-4 ${styles.border} bg-slate-50/60 p-3.5 transition hover:bg-slate-50`}
                      >
                        <div className="flex items-start gap-2.5">
                          <AlertCircle className={`mt-0.5 h-4 w-4 shrink-0 ${styles.icon}`} />
                          <div>
                            <p className="text-sm font-semibold text-slate-900">{issue.issue_type}</p>
                            <p className="mt-0.5 text-sm text-slate-600">{issue.description}</p>
                          </div>
                        </div>
                        <SeverityBadge severity={issue.severity} />
                      </div>
                    )
                  })}
                </div>

                <div className="mt-6 flex items-start gap-3 rounded-xl bg-gradient-to-r from-indigo-50 to-blue-50 p-4 ring-1 ring-inset ring-indigo-100">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-600 text-white">
                    <Sparkles className="h-4 w-4" />
                  </div>
                  <p className="text-sm text-indigo-900/80">
                    <span className="font-semibold text-indigo-900">Flagged for human review — </span>
                    4 deterministic issues detected. No automated action is taken without explicit human approval.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="relative overflow-hidden bg-[#0B1B3F]">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background:
              'radial-gradient(60% 50% at 15% 0%, rgba(59,130,246,0.25) 0%, rgba(11,27,63,0) 60%), radial-gradient(50% 40% at 100% 100%, rgba(16,185,129,0.18) 0%, rgba(11,27,63,0) 60%)',
          }}
        />

        <div className="relative mx-auto max-w-5xl px-6 py-20 text-center">
          <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-cyan-400">
            The Guardrail
          </p>
          <h2 className="mx-auto mt-3 max-w-2xl font-display text-2xl font-bold tracking-tight text-white md:text-4xl">
            AI recommends. The human decides. Automation executes.
          </h2>

          <div className="relative mt-14 flex flex-col items-center gap-5 sm:flex-row sm:items-stretch sm:justify-center sm:gap-0">
            <div className="absolute inset-x-16 top-8 hidden h-px bg-gradient-to-r from-indigo-400/40 via-blue-400/40 to-emerald-400/40 sm:block" />

            {[
              {
                icon: Sparkles,
                title: 'AI recommends',
                description: 'Grounded in deterministic rule findings — never a guess.',
                accent: 'from-indigo-500 to-violet-400',
              },
              {
                icon: UserCheck,
                title: 'The human decides',
                description: 'Every consequential action requires explicit approval.',
                accent: 'from-blue-500 to-cyan-400',
              },
              {
                icon: Zap,
                title: 'Automation executes',
                description: 'Only after approval — never before, never silently.',
                accent: 'from-emerald-500 to-teal-400',
              },
            ].map((step, i) => (
              <div key={step.title} className="group relative flex w-full max-w-xs flex-col items-center px-6 text-center sm:flex-1">
                <div
                  className={`relative z-10 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br ${step.accent} text-white shadow-lg shadow-black/20 ring-4 ring-[#0B1B3F] transition-transform duration-300 group-hover:scale-110`}
                >
                  <step.icon className="h-6 w-6" strokeWidth={2.25} />
                  <span className="absolute -right-2 -top-2 flex h-5 w-5 items-center justify-center rounded-full border-2 border-[#0B1B3F] bg-white font-mono text-[10px] font-bold text-slate-900">
                    {i + 1}
                  </span>
                </div>
                <p className="mt-5 font-display text-base font-bold text-white">{step.title}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-400">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-16 lg:grid-cols-2">
          <div>
            <p className="font-display text-sm font-bold uppercase tracking-[0.25em] text-indigo-600">
              Automation Layer
            </p>
            <h2 className="mt-3 font-display text-2xl font-bold tracking-tight text-slate-900 md:text-3xl">
              Approved actions, executed automatically.
            </h2>
            <p className="mt-4 text-sm leading-relaxed text-slate-500">
              Once a human approves a recommended action, Clyra's agent-routed automation layer — built on
              n8n workflows — carries it out: drafting a follow-up, logging a payer reminder, or updating
              claim status. Every execution ties back to the specific approval that authorized it, with a
              full audit trail.
            </p>
            <ul className="mt-5 space-y-2.5 text-sm text-slate-600">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                No action runs without human approval first
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                Every execution is logged with the approval that authorized it
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                Failures escalate to a human — never retried silently
              </li>
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <UserCheck className="h-5 w-5 shrink-0 text-indigo-600" />
              <p className="text-sm font-medium text-slate-700">Human approves recommended action</p>
            </div>
            <div className="ml-6 h-6 w-px bg-slate-200" />
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <Zap className="h-5 w-5 shrink-0 text-indigo-600" />
              <p className="text-sm font-medium text-slate-700">Agent-routed workflow executes the action</p>
            </div>
            <div className="ml-6 h-6 w-px bg-slate-200" />
            <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <CheckCircle2 className="h-5 w-5 shrink-0 text-indigo-600" />
              <p className="text-sm font-medium text-slate-700">Result logged to the claim's audit trail</p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-[#0B1B3F]">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="grid grid-cols-1 gap-10 text-center sm:grid-cols-3">
            <div>
              <p className="font-display text-4xl font-bold text-white md:text-5xl">32%</p>
              <p className="mt-2 text-sm text-slate-300">Reduction in claim denials</p>
            </div>
            <div>
              <p className="font-display text-4xl font-bold text-white md:text-5xl">$24,850</p>
              <p className="mt-2 text-sm text-slate-300">Revenue recovered this month</p>
            </div>
            <div>
              <p className="font-display text-4xl font-bold text-white md:text-5xl">12</p>
              <p className="mt-2 text-sm text-slate-300">Hours saved per week</p>
            </div>
          </div>
          <p className="mx-auto mt-10 max-w-md text-center text-xs text-slate-400">
            Illustrative example numbers for demo purposes — not measured production results.
          </p>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h2 className="font-display text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
            Stop chasing claims. Start resolving them.
          </h2>
          <p className="mx-auto mt-4 max-w-lg text-lg text-slate-500">
            See how Clyra brings deterministic risk scoring and human-approved automation to your claims
            pipeline.
          </p>
          <div className="mt-8">
            <Link
              to="/dashboard"
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600! px-8 py-3.5 text-sm font-semibold text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-500!"
            >
              Book a Demo
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>

      <footer className="relative overflow-hidden bg-[#0B1B3F]">
        <div
          className="pointer-events-none absolute inset-0 opacity-30"
          style={{
            background:
              'radial-gradient(40% 60% at 0% 0%, rgba(59,130,246,0.2) 0%, rgba(11,27,63,0) 60%)',
          }}
        />

        <div className="relative mx-auto max-w-6xl px-6 py-14">
          <div className="grid grid-cols-1 gap-10 sm:grid-cols-2 lg:grid-cols-4">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2.5">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/20">
                  <Plus className="h-5 w-5" strokeWidth={3} />
                </div>
                <p className="font-display text-lg font-bold text-white">Clyra</p>
              </div>
              <p className="mt-4 max-w-xs text-sm leading-relaxed text-slate-400">
                Deterministic risk scoring and AI-guided recommendations for health insurance claims
                teams — every consequential action still requires human approval.
              </p>
              <div className="mt-5 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3.5 py-1.5 text-xs font-medium text-slate-300">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                Demo environment — synthetic data only
              </div>
            </div>

            <div>
              <p className="font-display text-xs font-bold uppercase tracking-[0.2em] text-slate-500">Product</p>
              <ul className="mt-4 space-y-3">
                {navLinks.map((item) => (
                  <li key={item}>
                    <a
                      href={item === 'Product' ? '#how-it-works' : '#'}
                      className="text-sm text-slate-400 transition hover:text-white"
                    >
                      {item}
                    </a>
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <p className="font-display text-xs font-bold uppercase tracking-[0.2em] text-slate-500">
                Get Started
              </p>
              <ul className="mt-4 space-y-3">
                <li>
                  <Link to="/dashboard" className="text-sm text-slate-400 transition hover:text-white">
                    Sign in
                  </Link>
                </li>
                <li>
                  <Link to="/dashboard" className="text-sm text-slate-400 transition hover:text-white">
                    Book a Demo
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-white/10 pt-6 sm:flex-row">
            <p className="text-xs text-slate-500">© 2026 Clyra. All claims data is synthetic and privacy-safe.</p>
            <p className="text-xs text-slate-500">Built for health insurance billing and revenue-cycle teams.</p>
          </div>
        </div>
      </footer>
    </div>
  )
}
