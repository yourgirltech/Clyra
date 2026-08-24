export function HomePage() {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center">
      <div className="max-w-2xl rounded-2xl border border-slate-800 bg-slate-900/80 p-10 shadow-2xl">
        <p className="mb-3 text-sm uppercase tracking-[0.2em] text-cyan-400">Clyra</p>
        <h1 className="text-4xl font-bold text-white">AI claims operations assistant</h1>
        <p className="mt-4 text-lg text-slate-300">
          Human-approved AI guidance for healthcare billing and revenue-cycle teams.
        </p>
        <div className="mt-8 rounded-xl border border-slate-700 bg-slate-950 p-4 text-sm text-slate-300">
          Demo environment — uses synthetic healthcare claims data.
        </div>
      </div>
    </main>
  )
}
