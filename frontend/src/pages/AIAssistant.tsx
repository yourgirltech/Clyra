export function AIAssistant() {
  return (
    <div className="p-6 md:p-8">
      <div className="mb-6">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-indigo-600">AI Review</p>
        <h1 className="mt-2 text-3xl font-semibold text-slate-900">AI Assistant</h1>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-8 text-slate-600 shadow-sm">
        <p className="text-lg font-medium text-slate-700">AI Assistant — agentic reasoning layer, coming next</p>
        <p className="mt-2 text-sm text-slate-500">
          A LangGraph pipeline (Analyzer → Reasoning → Recommendation agents, plus a tool-calling Assistant
          agent) will surface explainable recommendations and rationale cards here, subject to human approval.
        </p>
      </div>
    </div>
  )
}
