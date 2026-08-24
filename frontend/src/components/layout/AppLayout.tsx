import { NavLink, Outlet } from 'react-router-dom'
import { Search, Plus, Bell, User } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/claims', label: 'Claims' },
  { to: '/ai-assistant', label: 'AI Assistant' },
  { to: '/settings', label: 'Settings' },
]

export function AppLayout() {
  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="w-full bg-slate-950 text-slate-200 md:w-72">
          <div className="flex items-center justify-between border-b border-slate-800 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500 text-lg font-semibold text-white shadow-lg shadow-indigo-500/30">
                <Plus className="h-4 w-4" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Clyra</p>
                <p className="text-sm font-medium text-white">Operations</p>
              </div>
            </div>
            <button className="rounded-lg border border-slate-700 p-2 text-slate-300 transition hover:border-slate-500 hover:text-white md:hidden">
              <Plus className="h-4 w-4 rotate-45" />
            </button>
          </div>

          <nav className="flex flex-col gap-2 p-4">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                    isActive
                      ? 'bg-indigo-500/15 text-indigo-200 ring-1 ring-indigo-400/30'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <div className="flex-1 bg-white">
          <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-4 md:px-8">
            <div className="flex w-full max-w-xl items-center gap-3 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
              <Search className="h-4 w-4 text-slate-400" />
              <input
                aria-label="Search"
                placeholder="Search claims, codes, alerts..."
                className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
              />
            </div>

            <div className="ml-4 flex items-center gap-3">
              <button className="rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:border-slate-300 hover:text-slate-900">
                <Bell className="h-4 w-4" />
              </button>
              <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-2 py-1.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
                  <User className="h-4 w-4" />
                </div>
                <div className="hidden text-left md:block">
                  <p className="text-xs text-slate-400">Signed in</p>
                  <p className="text-sm font-medium text-slate-700">A. Carter</p>
                </div>
              </div>
            </div>
          </header>

          <main className="bg-slate-50">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
