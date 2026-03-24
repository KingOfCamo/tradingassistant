import { useQuery } from '@tanstack/react-query';
import { Briefcase, ArrowUpRight, DollarSign, TrendingUp, PieChart } from 'lucide-react';
import { PieChart as RPieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { getToken } from '../hooks/useAuth.ts';

interface Position {
  id: string;
  symbol: string;
  name: string;
  side: 'LONG' | 'SHORT';
  qty: number;
  avgEntry: number;
  last: number;
  marketValue: number;
  pnl: number;
  pnlPct: number;
  weight: number;
  sector: string;
  daysHeld: number;
}

interface PortfolioData {
  positions: Position[];
  summary: {
    totalValue: number;
    totalCost: number;
    unrealizedPnl: number;
    unrealizedPnlPct: number;
    realizedPnlToday: number;
    cashBalance: number;
  };
}

const placeholder: PortfolioData = {
  positions: [
    { id: '1', symbol: 'BHP', name: 'BHP Group', side: 'LONG', qty: 200, avgEntry: 44.50, last: 45.80, marketValue: 9160, pnl: 260, pnlPct: 2.92, weight: 18.5, sector: 'Materials', daysHeld: 5 },
    { id: '2', symbol: 'CBA', name: 'Commonwealth Bank', side: 'LONG', qty: 50, avgEntry: 112.30, last: 110.85, marketValue: 5542.50, pnl: -72.50, pnlPct: -1.29, weight: 11.2, sector: 'Financials', daysHeld: 12 },
    { id: '3', symbol: 'WDS', name: 'Woodside Energy', side: 'SHORT', qty: 150, avgEntry: 27.60, last: 26.90, marketValue: 4035, pnl: 105, pnlPct: 2.54, weight: 8.1, sector: 'Energy', daysHeld: 3 },
    { id: '4', symbol: 'FMG', name: 'Fortescue', side: 'LONG', qty: 300, avgEntry: 18.90, last: 19.80, marketValue: 5940, pnl: 270, pnlPct: 4.76, weight: 12.0, sector: 'Materials', daysHeld: 8 },
    { id: '5', symbol: 'CSL', name: 'CSL Limited', side: 'LONG', qty: 20, avgEntry: 278.50, last: 282.00, marketValue: 5640, pnl: 70, pnlPct: 1.26, weight: 11.4, sector: 'Healthcare', daysHeld: 15 },
  ],
  summary: {
    totalValue: 248_520,
    totalCost: 240_880,
    unrealizedPnl: 632.50,
    unrealizedPnlPct: 0.26,
    realizedPnlToday: 580,
    cashBalance: 218_202.50,
  },
};

async function fetchPortfolio(): Promise<PortfolioData> {
  const token = getToken();
  const res = await fetch('/api/portfolio', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed');
  return res.json() as Promise<PortfolioData>;
}

const sectorColors: Record<string, string> = {
  Materials: '#00C896',
  Financials: '#3B82F6',
  Energy: '#F59E0B',
  Healthcare: '#8B5CF6',
  Consumer: '#06B6D4',
  Technology: '#F04B5A',
};

export default function Portfolio() {
  const { data } = useQuery({
    queryKey: ['portfolio'],
    queryFn: fetchPortfolio,
    refetchInterval: 30_000,
    placeholderData: placeholder,
  });
  const d = data ?? placeholder;

  // Sector allocation for pie chart
  const sectorMap = new Map<string, number>();
  for (const p of d.positions) {
    sectorMap.set(p.sector, (sectorMap.get(p.sector) ?? 0) + p.weight);
  }
  const pieData = [...sectorMap.entries()].map(([name, value]) => ({ name, value }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Briefcase className="w-5 h-5 text-accent-green" />
        <h1 className="text-lg font-semibold text-text-primary">Portfolio</h1>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-5 gap-4">
        <SummaryCard label="Total Value" value={`$${d.summary.totalValue.toLocaleString()}`} icon={<DollarSign className="w-4 h-4" />} />
        <SummaryCard
          label="Unrealized P&L"
          value={`${d.summary.unrealizedPnl >= 0 ? '+' : ''}$${d.summary.unrealizedPnl.toLocaleString()}`}
          sub={`${d.summary.unrealizedPnlPct >= 0 ? '+' : ''}${d.summary.unrealizedPnlPct.toFixed(2)}%`}
          valueColor={d.summary.unrealizedPnl >= 0 ? 'text-accent-green' : 'text-accent-red'}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <SummaryCard
          label="Realized Today"
          value={`${d.summary.realizedPnlToday >= 0 ? '+' : ''}$${d.summary.realizedPnlToday.toLocaleString()}`}
          valueColor={d.summary.realizedPnlToday >= 0 ? 'text-accent-green' : 'text-accent-red'}
          icon={<ArrowUpRight className="w-4 h-4" />}
        />
        <SummaryCard label="Cash Balance" value={`$${d.summary.cashBalance.toLocaleString()}`} icon={<DollarSign className="w-4 h-4" />} />
        <SummaryCard label="Positions" value={String(d.positions.length)} icon={<PieChart className="w-4 h-4" />} />
      </div>

      {/* Table + Allocation */}
      <div className="grid grid-cols-4 gap-4">
        {/* Positions table */}
        <div className="col-span-3 bg-bg-surface border border-border rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-border">
            <h3 className="text-sm font-semibold text-text-primary">Open Positions</h3>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-muted text-xs uppercase tracking-wider border-b border-border">
                <th className="text-left px-4 py-2.5 font-medium">Symbol</th>
                <th className="text-left px-4 py-2.5 font-medium">Side</th>
                <th className="text-right px-4 py-2.5 font-medium">Qty</th>
                <th className="text-right px-4 py-2.5 font-medium">Entry</th>
                <th className="text-right px-4 py-2.5 font-medium">Last</th>
                <th className="text-right px-4 py-2.5 font-medium">Mkt Val</th>
                <th className="text-right px-4 py-2.5 font-medium">P&L</th>
                <th className="text-right px-4 py-2.5 font-medium">Weight</th>
                <th className="text-right px-4 py-2.5 font-medium">Days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.positions.map((p) => (
                <tr key={p.id} className="hover:bg-bg-elevated/50 transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="font-semibold text-text-primary">{p.symbol}</div>
                    <div className="text-xs text-text-muted">{p.name}</div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${p.side === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'}`}>
                      {p.side}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right text-text-secondary">{p.qty}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-secondary">${p.avgEntry.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-primary">${p.last.toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-text-secondary">${p.marketValue.toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-right">
                    <div className={`font-mono font-medium ${p.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                      {p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}
                    </div>
                    <div className={`text-xs ${p.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                      {p.pnlPct >= 0 ? '+' : ''}{p.pnlPct.toFixed(2)}%
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-right text-text-secondary">{p.weight.toFixed(1)}%</td>
                  <td className="px-4 py-2.5 text-right text-text-muted">{p.daysHeld}d</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Sector allocation */}
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Sector Allocation</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <RPieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={70} paddingAngle={3} dataKey="value">
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={sectorColors[entry.name] ?? '#4A5568'} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [`${Number(v).toFixed(1)}%`, 'Weight']}
                />
              </RPieChart>
            </ResponsiveContainer>
          </div>
          <div className="space-y-2 mt-2">
            {pieData.map((s) => (
              <div key={s.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: sectorColors[s.name] ?? '#4A5568' }} />
                  <span className="text-text-secondary">{s.name}</span>
                </div>
                <span className="text-text-primary font-mono">{s.value.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, sub, icon, valueColor = 'text-text-primary' }: {
  label: string; value: string; sub?: string; icon: React.ReactNode; valueColor?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-text-muted text-xs uppercase tracking-wider font-medium">{label}</span>
        <span className="text-text-muted">{icon}</span>
      </div>
      <div className={`text-lg font-bold font-mono ${valueColor}`}>{value}</div>
      {sub && <div className={`text-xs mt-0.5 ${valueColor}`}>{sub}</div>}
    </div>
  );
}
