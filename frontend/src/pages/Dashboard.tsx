import { useQuery } from '@tanstack/react-query';
import {
  ArrowUpRight,
  ArrowDownRight,
  TrendingUp,
  Layers,
  FileText,
  Lightbulb,
  Briefcase,
  AlertTriangle,
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { getToken } from '../hooks/useAuth.ts';

// ---------- types ----------
interface Position {
  symbol: string;
  side: 'LONG' | 'SHORT';
  qty: number;
  avgEntry: number;
  last: number;
  pnl: number;
  pnlPct: number;
}

interface Idea {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  confluenceScore: number;
  strategy: string;
}

interface PortfolioSnapshot {
  totalValue: number;
  dayPnl: number;
  dayPnlPct: number;
  openPositions: number;
  equity: { date: string; value: number }[];
}

interface DashboardData {
  positions: Position[];
  confluence: { score: number; signals: number; topStrategy: string };
  morningBrief: string;
  topIdeas: Idea[];
  portfolio: PortfolioSnapshot;
}

// ---------- API ----------
async function fetchDashboard(): Promise<DashboardData> {
  const token = getToken();
  const res = await fetch('/api/dashboard', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed to load dashboard');
  return res.json() as Promise<DashboardData>;
}

// ---------- Placeholder data ----------
const placeholder: DashboardData = {
  positions: [
    { symbol: 'BHP', side: 'LONG', qty: 200, avgEntry: 44.50, last: 45.80, pnl: 260, pnlPct: 2.92 },
    { symbol: 'CBA', side: 'LONG', qty: 50, avgEntry: 112.30, last: 110.85, pnl: -72.5, pnlPct: -1.29 },
    { symbol: 'WDS', side: 'SHORT', qty: 150, avgEntry: 27.60, last: 26.90, pnl: 105, pnlPct: 2.54 },
  ],
  confluence: { score: 78, signals: 5, topStrategy: 'Mean Reversion' },
  morningBrief: 'ASX futures +0.3%. RBA minutes suggest hold in April. Iron ore steady at $108/t. US markets closed mixed, S&P 500 -0.1%. Key events today: NAB business confidence 11:30 AEST, US PCE data tonight. Watch for BHP and RIO on commodity strength. Regime: neutral with slight bullish tilt on materials.',
  topIdeas: [
    { id: '1', symbol: 'FMG', direction: 'LONG', confluenceScore: 85, strategy: 'Momentum' },
    { id: '2', symbol: 'CSL', direction: 'LONG', confluenceScore: 72, strategy: 'Mean Reversion' },
    { id: '3', symbol: 'WOW', direction: 'SHORT', confluenceScore: 68, strategy: 'Breakdown' },
  ],
  portfolio: {
    totalValue: 248_520,
    dayPnl: 1_230,
    dayPnlPct: 0.5,
    openPositions: 3,
    equity: [
      { date: 'Mon', value: 245000 },
      { date: 'Tue', value: 246200 },
      { date: 'Wed', value: 244800 },
      { date: 'Thu', value: 247300 },
      { date: 'Fri', value: 248520 },
    ],
  },
};

// ---------- helpers ----------
function pnlColor(val: number) {
  return val >= 0 ? 'text-accent-green' : 'text-accent-red';
}

function pnlBg(val: number) {
  return val >= 0 ? 'bg-accent-green/10' : 'bg-accent-red/10';
}

// ---------- component ----------
export default function Dashboard() {
  const { data } = useQuery({
    queryKey: ['dashboard'],
    queryFn: fetchDashboard,
    refetchInterval: 60_000,
    placeholderData: placeholder,
  });
  const d = data ?? placeholder;

  return (
    <div className="space-y-5">
      {/* Row 1: Stats + Equity */}
      <div className="grid grid-cols-4 gap-4">
        {/* Stat cards */}
        <StatCard
          label="Portfolio Value"
          value={`$${d.portfolio.totalValue.toLocaleString()}`}
          icon={<Briefcase className="w-4 h-4" />}
        />
        <StatCard
          label="Day P&L"
          value={`${d.portfolio.dayPnl >= 0 ? '+' : ''}$${d.portfolio.dayPnl.toLocaleString()}`}
          sub={`${d.portfolio.dayPnlPct >= 0 ? '+' : ''}${d.portfolio.dayPnlPct.toFixed(2)}%`}
          valueColor={pnlColor(d.portfolio.dayPnl)}
          icon={d.portfolio.dayPnl >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
        />
        <StatCard
          label="Open Positions"
          value={String(d.portfolio.openPositions)}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <StatCard
          label="Confluence"
          value={`${d.confluence.score}/100`}
          sub={`${d.confluence.signals} signals`}
          icon={<Layers className="w-4 h-4" />}
          valueColor="text-accent-blue"
        />
      </div>

      {/* Row 2: Equity chart + Morning brief */}
      <div className="grid grid-cols-3 gap-4">
        {/* Equity */}
        <div className="col-span-2 bg-bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Equity Curve (Week)</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={d.portfolio.equity}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00C896" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#00C896" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" tick={{ fill: '#8A9BB5', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis hide domain={['dataMin - 500', 'dataMax + 500']} />
                <Tooltip
                  contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#8A9BB5' }}
                  itemStyle={{ color: '#E2E8F0' }}
                  formatter={(v) => [`$${Number(v).toLocaleString()}`, 'Equity']}
                />
                <Area type="monotone" dataKey="value" stroke="#00C896" fill="url(#eqGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Morning brief */}
        <div className="bg-bg-surface border border-border rounded-xl p-5 flex flex-col">
          <div className="flex items-center gap-2 mb-3">
            <FileText className="w-4 h-4 text-accent-amber" />
            <h3 className="text-sm font-semibold text-text-primary">Morning Brief</h3>
          </div>
          <p className="text-text-secondary text-sm leading-relaxed flex-1">{d.morningBrief}</p>
          <button className="mt-4 text-xs text-accent-blue hover:underline self-start">Read full brief &rarr;</button>
        </div>
      </div>

      {/* Row 3: Positions today + Top ideas */}
      <div className="grid grid-cols-3 gap-4">
        {/* Positions */}
        <div className="col-span-2 bg-bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Positions Today</h3>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-text-muted text-xs uppercase tracking-wider">
                <th className="text-left pb-3 font-medium">Symbol</th>
                <th className="text-left pb-3 font-medium">Side</th>
                <th className="text-right pb-3 font-medium">Qty</th>
                <th className="text-right pb-3 font-medium">Avg Entry</th>
                <th className="text-right pb-3 font-medium">Last</th>
                <th className="text-right pb-3 font-medium">P&L</th>
                <th className="text-right pb-3 font-medium">%</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {d.positions.map((p) => (
                <tr key={p.symbol} className="hover:bg-bg-elevated/50 transition-colors">
                  <td className="py-2.5 font-medium text-text-primary">{p.symbol}</td>
                  <td className="py-2.5">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${p.side === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'}`}>
                      {p.side}
                    </span>
                  </td>
                  <td className="py-2.5 text-right text-text-secondary">{p.qty}</td>
                  <td className="py-2.5 text-right text-text-secondary font-mono">${p.avgEntry.toFixed(2)}</td>
                  <td className="py-2.5 text-right text-text-primary font-mono">${p.last.toFixed(2)}</td>
                  <td className={`py-2.5 text-right font-mono font-medium ${pnlColor(p.pnl)}`}>
                    {p.pnl >= 0 ? '+' : ''}${p.pnl.toFixed(2)}
                  </td>
                  <td className="py-2.5 text-right">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${pnlBg(p.pnl)} ${pnlColor(p.pnl)}`}>
                      {p.pnlPct >= 0 ? '+' : ''}{p.pnlPct.toFixed(2)}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.positions.length === 0 && (
            <p className="text-text-muted text-sm text-center py-6">No open positions today</p>
          )}
        </div>

        {/* Top ideas */}
        <div className="bg-bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Lightbulb className="w-4 h-4 text-accent-purple" />
            <h3 className="text-sm font-semibold text-text-primary">Top Ideas</h3>
          </div>
          <div className="space-y-3">
            {d.topIdeas.map((idea) => (
              <div key={idea.id} className="bg-bg-elevated rounded-lg p-3 flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-semibold text-sm">{idea.symbol}</span>
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${idea.direction === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'}`}>
                      {idea.direction}
                    </span>
                  </div>
                  <span className="text-text-muted text-xs">{idea.strategy}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <div className="w-8 h-8 rounded-full border-2 border-accent-blue flex items-center justify-center">
                    <span className="text-xs font-bold text-accent-blue">{idea.confluenceScore}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
          {d.topIdeas.length === 0 && (
            <div className="flex flex-col items-center py-8 text-text-muted">
              <AlertTriangle className="w-6 h-6 mb-2" />
              <span className="text-sm">No ideas today</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- Stat card ----------
function StatCard({
  label,
  value,
  sub,
  icon,
  valueColor = 'text-text-primary',
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ReactNode;
  valueColor?: string;
}) {
  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-text-muted text-xs uppercase tracking-wider font-medium">{label}</span>
        <span className="text-text-muted">{icon}</span>
      </div>
      <div className={`text-xl font-bold font-mono ${valueColor}`}>{value}</div>
      {sub && <div className={`text-xs mt-0.5 ${valueColor}`}>{sub}</div>}
    </div>
  );
}
