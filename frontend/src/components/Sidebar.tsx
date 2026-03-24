import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Lightbulb,
  Layers,
  Search,
  Star,
  Briefcase,
  ShieldAlert,
  BookOpen,
  BrainCircuit,
  Settings,
  LogOut,
  TrendingUp,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth.ts';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/ideas', label: 'Ideas', icon: Lightbulb },
  { to: '/confluence', label: 'Confluence', icon: Layers },
  { to: '/screener', label: 'Screener', icon: Search },
  { to: '/watchlist', label: 'Watchlist', icon: Star },
  { to: '/portfolio', label: 'Portfolio', icon: Briefcase },
  { to: '/risk', label: 'Risk Map', icon: ShieldAlert },
  { to: '/journal', label: 'Journal', icon: BookOpen },
  { to: '/analysis', label: 'Analysis', icon: BrainCircuit },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
  const { logout } = useAuth();

  return (
    <aside className="fixed left-0 top-0 bottom-0 w-60 bg-bg-surface border-r border-border flex flex-col z-40">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 h-14 border-b border-border shrink-0">
        <TrendingUp className="w-6 h-6 text-accent-green" />
        <span className="text-text-primary font-semibold text-base tracking-tight">
          TradeDesk
        </span>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-3 space-y-0.5">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-accent-green/10 text-accent-green'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'
              }`
            }
          >
            <Icon className="w-4.5 h-4.5 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-3">
        <button
          onClick={() => { void logout(); }}
          className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-text-secondary hover:text-accent-red hover:bg-accent-red/10 transition-colors w-full"
        >
          <LogOut className="w-4.5 h-4.5" />
          Logout
        </button>
      </div>
    </aside>
  );
}
