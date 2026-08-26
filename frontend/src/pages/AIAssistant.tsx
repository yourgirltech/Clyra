import { useEffect, useRef, useState } from 'react'
import type React from 'react'
import { Bot, Loader2, Send, Sparkles, User } from 'lucide-react'
import { askAssistant } from '../services/assistant'
import type { ChatHistoryMessage } from '../services/assistant'

type ChatMessage = {
  role: 'assistant' | 'user'
  text: string
  ok?: boolean
}

const seedMessages: ChatMessage[] = [
  {
    role: 'assistant',
    text: "Hi, I'm the Clyra assistant. Ask me about a claim, a risk factor, or portfolio metrics — I'll ground every answer in real claim data and tell you plainly when I don't have enough information, rather than guess.",
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
  const [messages, setMessages] = useState<ChatMessage[]>(seedMessages)
  const [draft, setDraft] = useState('')
  const [sending, setSending] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, sending])

  const send = async (text: string) => {
    const question = text.trim()
    if (!question || sending) return

    const history: ChatHistoryMessage[] = messages.map((m) => ({
      role: m.role,
      content: m.text,
    }))

    setMessages((prev) => [...prev, { role: 'user', text: question }])
    setDraft('')
    setSending(true)

    try {
      const response = await askAssistant(question, history)
      setMessages((prev) => [...prev, { role: 'assistant', text: response.reply, ok: response.ok }])
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          text: "I couldn't reach the AI Assistant just now — check that the backend is running and try again.",
          ok: false,
        },
      ])
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    send(draft)
  }

  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">AI Review</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">AI Assistant</h1>
        <p className="mt-1 text-sm text-slate-500">
          Ask about a claim, a risk factor, or portfolio metrics. Read-only — it never takes action for you.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
        <div className="flex h-[560px] flex-col rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto p-6">
            {messages.map((m, i) => (
              <div key={i} className={`flex items-start gap-3 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${
                    m.role === 'assistant' ? 'bg-indigo-100 text-indigo-700' : 'bg-slate-100 text-slate-600'
                  }`}
                >
                  {m.role === 'assistant' ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
                </div>
                <div
                  className={`max-w-[80%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'bg-indigo-500 text-white'
                      : m.ok === false
                        ? 'bg-amber-50 text-amber-800'
                        : 'bg-slate-50 text-slate-700'
                  }`}
                >
                  {m.text}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex items-start gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="flex items-center gap-2 rounded-2xl bg-slate-50 px-4 py-3 text-sm text-slate-500">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  Looking that up…
                </div>
              </div>
            )}
          </div>

          <form onSubmit={handleSubmit} className="border-t border-slate-100 p-4">
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:border-indigo-300 focus-within:ring-2 focus-within:ring-indigo-100">
              <input
                ref={inputRef}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                disabled={sending}
                placeholder="Ask about a claim, a risk factor, or portfolio metrics…"
                className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={sending || !draft.trim()}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500 text-white transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:bg-indigo-300"
              >
                {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              </button>
            </div>
          </form>
        </div>

        <div className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Sparkles className="h-4 w-4 text-indigo-500" />
              Try asking
            </div>
            <ul className="mt-3 space-y-2.5">
              {sampleQuestions.map((q) => (
                <li key={q}>
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => send(q)}
                    className="w-full rounded-xl border border-dashed border-slate-200 bg-slate-50 px-3 py-2.5 text-left text-sm text-slate-500 transition hover:border-indigo-200 hover:bg-indigo-50/60 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {q}
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-dashed border-indigo-200 bg-indigo-50/60 p-5 text-sm text-indigo-700/80">
            Every answer is grounded in real claim data — the actual rule-engine findings and dashboard
            metrics, not general knowledge. If it doesn't have enough information to answer, it says so
            instead of guessing, and it can't take any action on your behalf.
          </div>
        </div>
      </div>
    </div>
  )
}
