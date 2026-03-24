import { useState } from 'react';
import { Star, Plus, ArrowUpRight, ArrowDownRight, Bell, Trash2 } from 'lucide-react';

interface WatchlistItem {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  alertPrice: number | null;
  notes: string;
}

interface WatchlistGroup {
  id: string;
  name: string;
  items: WatchlistItem[];
}

const placeholderGroups: WatchlistGroup[] = [
  {
    id: '1',
    name: 'Materials',
    items: [
      { symbol: 'BHP', name: 'BHP Group', price: 45.80, change: 0.85, changePct: 1.89, alertPrice: 47.00, notes: 'Watch for breakout above 46.50' },
      { symbol: 'FMG', name: 'Fortescue', price: 19.80, change: 0.62, changePct: 3.23, alertPrice: 20.50, notes: 'Iron ore momentum play' },
      { symbol: 'RIO', name: 'Rio Tinto', price: 118.50, change: 2.10, changePct: 1.81, alertPrice: null, notes: '' },
    ],
  },
  {
    id: '2',
    name: 'Financials',
    items: [
      { symbol: 'CBA', name: 'Commonwealth Bank', price: 110.85, change: -1.45, changePct: -1.29, alertPrice: 108.00, notes: 'Support at 108' },
      { symbol: 'NAB', name: 'National Australia Bank', price: 37.20, change: 0.15, changePct: 0.40, alertPrice: null, notes: 'Earnings next week' },
    ],
  },
  {
    id: '3',
    name: 'Short Candidates',
    items: [
      { symbol: 'WOW', name: 'Woolworths', price: 31.50, change: -0.42, changePct: -1.32, alertPrice: 30.00, notes: 'H&S pattern forming' },
      { symbol: 'STO', name: 'Santos', price: 6.85, change: -0.15, changePct: -2.14, alertPrice: null, notes: 'Oil weakness' },
    ],
  },
];

export default function Watchlist() {
  const [groups] = useState(placeholderGroups);
  const [expandedGroup, setExpandedGroup] = useState<string | null>('1');

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Star className="w-5 h-5 text-accent-amber" />
          <h1 className="text-lg font-semibold text-text-primary">Watchlist</h1>
        </div>
        <button className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-green/10 text-accent-green rounded-lg text-sm font-medium hover:bg-accent-green/20 transition-colors">
          <Plus className="w-4 h-4" />
          New Group
        </button>
      </div>

      {/* Groups */}
      <div className="space-y-3">
        {groups.map((group) => (
          <div key={group.id} className="bg-bg-surface border border-border rounded-xl overflow-hidden">
            {/* Group header */}
            <button
              onClick={() => setExpandedGroup(expandedGroup === group.id ? null : group.id)}
              className="w-full flex items-center justify-between px-4 py-3 hover:bg-bg-elevated/30 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-text-primary">{group.name}</span>
                <span className="text-xs text-text-muted bg-bg-elevated px-2 py-0.5 rounded-full">
                  {group.items.length}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={(e) => { e.stopPropagation(); }}
                  className="p-1 text-text-muted hover:text-accent-green transition-colors"
                >
                  <Plus className="w-4 h-4" />
                </button>
                <svg className={`w-4 h-4 text-text-muted transition-transform ${expandedGroup === group.id ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </button>

            {/* Items */}
            {expandedGroup === group.id && (
              <div className="border-t border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-text-muted text-xs uppercase tracking-wider">
                      <th className="text-left px-4 py-2 font-medium">Symbol</th>
                      <th className="text-right px-4 py-2 font-medium">Price</th>
                      <th className="text-right px-4 py-2 font-medium">Change</th>
                      <th className="text-right px-4 py-2 font-medium">Alert</th>
                      <th className="text-left px-4 py-2 font-medium">Notes</th>
                      <th className="w-20 px-4 py-2"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {group.items.map((item) => (
                      <tr key={item.symbol} className="hover:bg-bg-elevated/30 transition-colors">
                        <td className="px-4 py-2.5">
                          <div className="font-semibold text-text-primary">{item.symbol}</div>
                          <div className="text-xs text-text-muted">{item.name}</div>
                        </td>
                        <td className="px-4 py-2.5 text-right font-mono text-text-primary">${item.price.toFixed(2)}</td>
                        <td className="px-4 py-2.5 text-right">
                          <span className={`inline-flex items-center gap-1 font-mono text-xs ${item.change >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                            {item.change >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                            {item.changePct >= 0 ? '+' : ''}{item.changePct.toFixed(2)}%
                          </span>
                        </td>
                        <td className="px-4 py-2.5 text-right">
                          {item.alertPrice ? (
                            <span className="inline-flex items-center gap-1 text-xs text-accent-amber">
                              <Bell className="w-3 h-3" />
                              ${item.alertPrice.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-text-muted text-xs">--</span>
                          )}
                        </td>
                        <td className="px-4 py-2.5 text-text-secondary text-xs max-w-[200px] truncate">{item.notes || '--'}</td>
                        <td className="px-4 py-2.5">
                          <div className="flex items-center gap-1 justify-end">
                            <button className="p-1 text-text-muted hover:text-accent-amber transition-colors">
                              <Bell className="w-3.5 h-3.5" />
                            </button>
                            <button className="p-1 text-text-muted hover:text-accent-red transition-colors">
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Quick add */}
      <div className="bg-bg-surface border border-border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Quick Add</h3>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Enter symbol (e.g. BHP)"
            className="flex-1 bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-green/50 focus:ring-1 focus:ring-accent-green/20 transition"
          />
          <select className="bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none focus:border-accent-green/50 transition">
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
          <button className="flex items-center gap-1.5 px-4 py-2 bg-accent-green text-bg-base rounded-lg text-sm font-semibold hover:brightness-110 transition">
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
