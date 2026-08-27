import { Fragment } from 'react'
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
  { icon: FileText, title: 'Claim Submitted', description: 'A new claim enters the pipeline with its evidence and payer requirements.' },
  { icon: Bot, title: 'AI Analyzes', description: 'The deterministic rule engine scores risk and surfaces issues automatically.' },
  { icon: AlertCircle, title: 'Issue Identified', description: 'Missing authorization, documentation gaps, or coding mismatches are flagged.' },
  { icon: UserCheck, title: 'Human Review', description: 'A reviewer sees the evidence and decides — no action happens without approval.' },
  { icon: Zap, title: 'Automation Executes', description: 'Once approved, the agent-routed automation layer carries out the action.' },
  { icon: CheckCircle2, title: 'Resolution & Recovery', description: 'The claim moves toward payment, with a full audit trail of every step.' },
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
    title: 'Deterministic risk scoring',
    description:
      'Every claim is scored by a transparent rule engine first — issues, severity, and risk level are computed the same way every time, before any AI touches the claim.',
  },
  {
    icon: Sparkles,
    title: 'Explainable AI reasoning',
    description:
      'AI agents explain what the rule engine found and propose next steps, always tracing back to the specific evidence that grounds each statement.',
  },
  {
    icon: UserCheck,
    title: 'Human-approved actions',
    description:
      'AI recommends, your team decides. No follow-up, reminder, or status change ever executes without an explicit human approval.',
  },
  {
    icon: ClipboardCheck,
    title: 'Full audit trail',
    description:
      'Every recommendation, approval, and executed action is logged with the evidence behind it, so any decision can be traced and reviewed after the fact.',
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
            <p className="text-lg font-semibold text-slate-900">Clyra</p>
          </div>

          <nav className="hidden items-center gap-8 lg:flex">
            {navLinks.map((item) => (
              <a
                key={item}
                href={item === 'Product' ? '#how-it-works' : '#'}
                className="text-sm font-medium text-slate-600 transition hover:text-slate-900"
              >
                {item}
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

      <section className="bg-white">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-6 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <span className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.15em] text-blue-700">
              AI Health Insurance Claims Operations
            </span>
            <h1 className="mt-6 text-4xl font-bold leading-tight tracking-tight text-slate-900 md:text-5xl">
              Clear, explainable health insurance claim risk —{' '}
              <span className="text-blue-600">decided by your team.</span>
            </h1>
            <p className="mt-5 max-w-lg text-lg text-slate-500">
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
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-6 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
              >
                <PlayCircle className="h-4 w-4" />
                See How It Works
              </a>
            </div>
            <div className="mt-8 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-4 py-2 text-xs font-medium text-slate-500">
              Demo environment — synthetic data only
            </div>
          </div>

          <div>
            <img
              src="/hero-visual.png"
              alt="Clyra dashboard showing claim risk scores, recovered totals, and claims needing attention"
              className="w-full rounded-2xl"
            />
          </div>
        </div>
      </section>

      <section id="how-it-works" className="bg-slate-50">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="mb-10 text-center">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Capabilities</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900 md:text-3xl">
              Smarter Claims. Stronger Revenue.
            </h2>
          </div>

          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <div
                key={f.title}
                className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:border-slate-300"
              >
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                  <f.icon className="h-5 w-5" />
                </div>
                <h3 className="mt-4 text-sm font-semibold text-slate-900">{f.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-500">{f.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-6xl px-6 py-16">
          <div className="mb-12 text-center">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">The Workflow</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900 md:text-3xl">
              From Claim to Resolution — Seamlessly
            </h2>
          </div>

          <div className="flex gap-4 overflow-x-auto pb-2 lg:gap-2 lg:overflow-visible">
            {processSteps.map((step, i) => (
              <Fragment key={step.title}>
                <div className="w-48 shrink-0 rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm lg:w-auto lg:flex-1">
                  <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                    <step.icon className="h-5 w-5" />
                  </div>
                  <p className="mt-3 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                    Step {i + 1}
                  </p>
                  <h3 className="mt-1 text-sm font-semibold text-slate-900">{step.title}</h3>
                  <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{step.description}</p>
                </div>
                {i < processSteps.length - 1 && (
                  <div className="hidden shrink-0 items-center justify-center pt-16 text-slate-300 lg:flex">
                    <ArrowRight className="h-4 w-4" />
                  </div>
                )}
              </Fragment>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto max-w-4xl px-6 py-16">
          <div className="mb-10 text-center">
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">See It In Action</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900 md:text-3xl">
              A real claim, analyzed by the real rule engine.
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500">
              Pulled directly from our synthetic demo dataset — the same deterministic engine that powers
              every claim in the live dashboard.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm md:p-8">
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-100 pb-5">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Claim ID</p>
                <p className="mt-1 text-lg font-semibold text-slate-900">{demoClaim.claimId}</p>
                <p className="mt-0.5 text-sm text-slate-500">
                  {demoClaim.patient} · {demoClaim.payer} · ${demoClaim.amount.toFixed(2)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <RiskBadge level={demoClaim.riskLevel} />
                <span className="text-2xl font-bold text-red-600">{demoClaim.riskScore}%</span>
              </div>
            </div>

            <div className="mt-5 space-y-2.5">
              {demoClaim.issues.map((issue) => (
                <div
                  key={issue.issue_type}
                  className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3.5"
                >
                  <div className="flex items-start gap-2.5">
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{issue.issue_type}</p>
                      <p className="mt-0.5 text-sm text-slate-600">{issue.description}</p>
                    </div>
                  </div>
                  <SeverityBadge severity={issue.severity} />
                </div>
              ))}
            </div>

            <div className="mt-5 flex items-start gap-3 rounded-xl border border-dashed border-indigo-200 bg-indigo-50/60 p-4">
              <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
              <p className="text-sm text-indigo-700/80">
                <span className="font-semibold text-indigo-900">Flagged for human review — </span>
                4 deterministic issues detected. No automated action is taken without explicit human approval.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-white">
        <div className="mx-auto max-w-5xl px-6 py-16 text-center">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">The Guardrail</p>
          <h2 className="mx-auto mt-2 max-w-2xl text-2xl font-semibold text-slate-900 md:text-3xl">
            AI recommends. The human decides. Automation executes.
          </h2>

          <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:items-stretch sm:justify-center">
            {[
              { icon: Sparkles, title: 'AI recommends', description: 'Grounded in deterministic rule findings — never a guess.' },
              { icon: UserCheck, title: 'The human decides', description: 'Every consequential action requires explicit approval.' },
              { icon: Zap, title: 'Automation executes', description: 'Only after approval — never before, never silently.' },
            ].map((step, i, arr) => (
              <Fragment key={step.title}>
                <div className="flex w-full max-w-xs flex-col items-center rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                    <step.icon className="h-5 w-5" />
                  </div>
                  <p className="mt-3 font-semibold text-slate-900">{step.title}</p>
                  <p className="mt-1.5 text-sm text-slate-500">{step.description}</p>
                </div>
                {i < arr.length - 1 && (
                  <div className="hidden shrink-0 items-center text-slate-300 sm:flex">
                    <ArrowRight className="h-5 w-5" />
                  </div>
                )}
              </Fragment>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50">
        <div className="mx-auto grid max-w-6xl grid-cols-1 items-center gap-10 px-6 py-16 lg:grid-cols-2">
          <div>
            <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">Automation Layer</p>
            <h2 className="mt-2 text-2xl font-semibold text-slate-900 md:text-3xl">
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
              <p className="text-4xl font-bold text-white md:text-5xl">32%</p>
              <p className="mt-2 text-sm text-slate-300">Reduction in claim denials</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-white md:text-5xl">$24,850</p>
              <p className="mt-2 text-sm text-slate-300">Revenue recovered this month</p>
            </div>
            <div>
              <p className="text-4xl font-bold text-white md:text-5xl">12</p>
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
          <h2 className="text-3xl font-bold tracking-tight text-slate-900 md:text-4xl">
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

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-8 text-sm text-slate-400">
          Clyra — demo environment. All claims data is synthetic and privacy-safe.
        </div>
      </footer>
    </div>
  )
}
