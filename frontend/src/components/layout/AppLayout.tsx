import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { Bell, Bot, FileStack, LayoutDashboard, Menu, Plus, Search, Settings2, User, X } from 'lucide-react'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/claims', label: 'Claims', icon: FileStack },
  { to: '/ai-assistant', label: 'AI Assistant', icon: Bot },
  { to: '/settings', label: 'Settings', icon: Settings2 },
]

export function AppLayout() {
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="w-full bg-[#0B1B3F] text-slate-200 md:w-64 md:shrink-0">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-5">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/30">
                <Plus className="h-5 w-5" strokeWidth={3} />
              </div>
              <p className="text-lg font-semibold text-white">Clyra</p>
            </div>
            <button
              onClick={() => setMobileNavOpen((v) => !v)}
              aria-label={mobileNavOpen ? 'Close navigation' : 'Open navigation'}
              className="rounded-lg border border-white/10 p-2 text-slate-300 transition hover:border-white/30 hover:text-white md:hidden"
            >
              {mobileNavOpen ? <X className="h-4 w-4" /> : <Menu className="h-4 w-4" />}
            </button>
          </div>

          <nav className={`flex-col gap-1 p-3 ${mobileNavOpen ? 'flex' : 'hidden'} md:flex`}>
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileNavOpen(false)}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${
                    isActive
                      ? 'bg-gradient-to-r from-blue-600 to-blue-500 text-white shadow-md shadow-blue-900/30'
                      : 'text-slate-300 hover:bg-white/5 hover:text-white'
                  }`
                }
              >
                <item.icon className="h-4 w-4" />
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
                placeholder="Search claims, patients..."
                className="w-full border-0 bg-transparent text-sm text-slate-700 placeholder:text-slate-400 focus:outline-none"
              />
            </div>

            <div className="ml-4 flex items-center gap-3">
              <button className="relative rounded-lg border border-slate-200 p-2 text-slate-600 transition hover:border-slate-300 hover:text-slate-900">
                <Bell className="h-4 w-4" />
                <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-semibold text-white">
                  1
                </span>
              </button>
              <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-slate-50 px-2 py-1.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-xs font-semibold text-blue-700">
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
