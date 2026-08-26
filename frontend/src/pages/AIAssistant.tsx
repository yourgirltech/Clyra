import { useState } from 'react'
import { Bot, Lock, Send, Sparkles, User } from 'lucide-react'

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
}

const seedMessages: ChatMessage[] = [
  {
    role: 'assistant',
    text: "Hi, I'm the Clyra assistant. Once I'm connected, I'll answer questions about your claims using real claim data — and tell you plainly when I don't have enough information, rather than guess.",
  },
]

const sampleQuestions = [
  'Which claims need my attention today?',
  'Why was this claim flagged?',
  'Show me my highest-risk claims.',
  'Which claims are waiting too long?',
  'What should I review first?',
]

export function AIAssistant() {
  const [draft, setDraft] = useState('')

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">AI Review</p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900">AI Assistant</h1>
          <p className="mt-1 text-sm text-slate-500">
            Ask about a claim, a risk factor, or portfolio metrics. Read-only — it never takes action for you.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-medium text-amber-700">
          <Lock className="h-3.5 w-3.5" />
          Not yet connected
        </span>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
        <div className="flex h-[560px] flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex-1 space-y-4 overflow-y-auto p-6">
            {seedMessages.map((m, i) => (
              <div key={i} className={`flex items-start gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    m.role === 'assistant' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {m.role === 'assistant' ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
                </div>
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === 'assistant'
                      ? 'bg-slate-50 text-slate-700'
                      : 'bg-indigo-500 text-white'
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-slate-100 p-4">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 opacity-60">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled
                placeholder="Assistant agent not connected yet"
                className="w-full border-0 bg-transparent text-sm text-slate-600 placeholder:text-slate-400 focus:outline-none"
              />
              <button
                disabled
                className="flex h-8 w-8 shrink-0 cursor-not-allowed items-center justify-center rounded-lg bg-indigo-300 text-white"
              >
                <Send className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Sparkles className="h-4 w-4 text-indigo-500" />
              What it will answer
            </div>
            <ul className="mt-3 space-y-2.5">
              {sampleQuestions.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    onClick={() => setDraft(q)}
                    className="w-full rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2.5 text-left text-sm text-slate-500 transition hover:border-indigo-200 hover:bg-indigo-50/60 hover:text-indigo-700"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 p-5 text-sm text-indigo-700/80">
            Every answer will be grounded in real claim data — the actual rule-engine findings and dashboard
            metrics, not general knowledge. If it doesn't have enough information to answer, it says so instead
            of guessing.
          </div>
        </div>
      </div>
    </div>
  )
}
