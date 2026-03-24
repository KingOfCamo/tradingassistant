import { useState } from 'react';
import { BookOpen, Plus, Calendar, TrendingUp, TrendingDown, Filter, XCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';

type TradeResult = 'win' | 'loss' | 'breakeven';
type PassReason = 'Low Confluence' | 'Bad Regime' | 'Position Sizing' | 'Correlation' | 'Timing' | 'No Edge';

interface JournalEntry {
  id: string;
  date: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  result: TradeResult;
  pnl: number;
  strategy: string;
  setup: string;
  notes: string;
  passReason: PassReason | null;
  entryPrice: number;
  exitPrice: number;
  holdDays: number;
}

const placeholderEntries: JournalEntry[] = [
  { id: '1', date: '2024-03-24', symbol: 'BHP', direction: 'LONG', result: 'win', pnl: 420, strategy: 'Momentum', setup: 'Breakout above resistance', notes: 'Clean entry on volume. Held through pullback.', passReason: null, entryPrice: 44.50, exitPrice: 46.60, holdDays: 5 },
  { id: '2', date: '2024-03-23', symbol: 'WOW', direction: 'SHORT', result: 'loss', pnl: -180, strategy: 'Breakdown', setup: 'H&S neckline break', notes: 'Stopped out on reversal. Entry was too early.', passReason: null, entryPrice: 32.10, exitPrice: 32.70, holdDays: 2 },
  { id: '3', date: '2024-03-22', symbol: 'CSL', direction: 'LONG', result: 'win', pnl: 310, strategy: 'Mean Reversion', setup: 'RSI oversold bounce', notes: 'Good risk/reward. Took partial at 1.5R.', passReason: null, entryPrice: 275.00, exitPrice: 282.00, holdDays: 4 },
  { id: '4', date: '2024-03-22', symbol: 'ALL', direction: 'LONG', result: 'breakeven', pnl: 5, strategy: 'Breakout', setup: 'Triangle breakout', notes: 'Moved to breakeven stop. No follow through.', passReason: null, entryPrice: 46.00, exitPrice: 46.02, holdDays: 1 },
  { id: '5', date: '2024-03-21', symbol: 'RIO', direction: 'LONG', result: 'win', pnl: 290, strategy: 'Momentum', setup: 'Sector rotation', notes: 'Materials strength. Rode the trend.', passReason: null, entryPrice: 115.20, exitPrice: 118.50, holdDays: 7 },
];

const passReasonData: { reason: PassReason; count: number }[] = [
  { reason: 'Low Confluence', count: 12 },
  { reason: 'Bad Regime', count: 8 },
  { reason: 'Position Sizing', count: 5 },
  { reason: 'Correlation', count: 4 },
  { reason: 'Timing', count: 3 },
  { reason: 'No Edge', count: 7 },
];

const resultColors: Record<TradeResult, string> = {
  win: '#00C896',
  loss: '#F04B5A',
  breakeven: '#F59E0B',
};

export default function Journal() {
  const [filterResult, setFilterResult] = useState<TradeResult | 'all'>('all');
  const entries = placeholderEntries;
  const filtered = filterResult === 'all' ? entries : entries.filter((e) => e.result === filterResult);

  const winCount = entries.filter((e) => e.result === 'win').length;
  const lossCount = entries.filter((e) => e.result === 'loss').length;
  const beCount = entries.filter((e) => e.result === 'breakeven').length;
  const totalPnl = entries.reduce((s, e) => s + e.pnl, 0);
  const winRate = entries.length > 0 ? ((winCount / entries.length) * 100).toFixed(0) : '0';

  const pieData = [
    { name: 'Win', value: winCount },
    { name: 'Loss', value: lossCount },
    { name: 'B/E', value: beCount },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="w-5 h-5 text-accent-blue" />
          <h1 className="text-lg font-semibold text-text-primary">Trade Journal</h1>
        </div>
        <button className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-green/10 text-accent-green rounded-lg text-sm font-medium hover:bg-accent-green/20 transition-colors">
          <Plus className="w-4 h-4" />
          New Entry
        </button>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-5 gap-4">
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">Total Trades</div>
          <div className="text-xl font-bold font-mono text-text-primary">{entries.length}</div>
        </div>
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">Win Rate</div>
          <div className="text-xl font-bold font-mono text-accent-green">{winRate}%</div>
        </div>
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">Total P&L</div>
          <div className={`text-xl font-bold font-mono ${totalPnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
            {totalPnl >= 0 ? '+' : ''}${totalPnl.toLocaleString()}
          </div>
        </div>
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">Avg Win</div>
          <div className="text-xl font-bold font-mono text-accent-green">
            +${winCount > 0 ? Math.round(entries.filter((e) => e.result === 'win').reduce((s, e) => s + e.pnl, 0) / winCount) : 0}
          </div>
        </div>
        <div className="bg-bg-surface border border-border rounded-xl p-4">
          <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">Avg Loss</div>
          <div className="text-xl font-bold font-mono text-accent-red">
            ${lossCount > 0 ? Math.round(entries.filter((e) => e.result === 'loss').reduce((s, e) => s + e.pnl, 0) / lossCount) : 0}
          </div>
        </div>
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-2 gap-4">
        {/* Win/Loss pie */}
        <div className="bg-bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3">Result Distribution</h3>
          <div className="h-44 flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={40} outerRadius={65} paddingAngle={4} dataKey="value">
                  {pieData.map((entry) => (
                    <Cell key={entry.name} fill={resultColors[entry.name.toLowerCase() === 'b/e' ? 'breakeven' : entry.name.toLowerCase() as TradeResult]} />
                  ))}
                </Pie>
                <Tooltip contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex items-center justify-center gap-4 mt-2 text-xs">
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-accent-green" /> Win ({winCount})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-accent-red" /> Loss ({lossCount})</span>
            <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-accent-amber" /> B/E ({beCount})</span>
          </div>
        </div>

        {/* Pass reason analytics */}
        <div className="bg-bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-3">
            <XCircle className="w-4 h-4 text-accent-red" />
            <h3 className="text-sm font-semibold text-text-primary">Pass Reasons (Last 30d)</h3>
          </div>
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={passReasonData} layout="vertical">
                <XAxis type="number" tick={{ fill: '#8A9BB5', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="reason" tick={{ fill: '#8A9BB5', fontSize: 10 }} width={100} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#8B5CF6" fillOpacity={0.7} radius={[0, 4, 4, 0]} barSize={16} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-text-muted" />
        {(['all', 'win', 'loss', 'breakeven'] as const).map((r) => (
          <button
            key={r}
            onClick={() => setFilterResult(r)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filterResult === r ? 'bg-accent-blue/15 text-accent-blue' : 'text-text-secondary hover:bg-bg-elevated'
            }`}
          >
            {r === 'all' ? 'All' : r === 'breakeven' ? 'B/E' : r.charAt(0).toUpperCase() + r.slice(1)}
          </button>
        ))}
      </div>

      {/* Journal entries */}
      <div className="space-y-3">
        {filtered.map((entry) => (
          <div key={entry.id} className="bg-bg-surface border border-border rounded-xl p-4 hover:border-border/80 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${
                  entry.result === 'win' ? 'bg-accent-green/10' : entry.result === 'loss' ? 'bg-accent-red/10' : 'bg-accent-amber/10'
                }`}>
                  {entry.result === 'win' ? <TrendingUp className="w-4 h-4 text-accent-green" /> :
                   entry.result === 'loss' ? <TrendingDown className="w-4 h-4 text-accent-red" /> :
                   <TrendingUp className="w-4 h-4 text-accent-amber" />}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-text-primary">{entry.symbol}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      entry.direction === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'
                    }`}>{entry.direction}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-accent-purple/10 text-accent-purple">{entry.strategy}</span>
                  </div>
                  <div className="text-xs text-text-muted mt-0.5">{entry.setup}</div>
                </div>
              </div>

              <div className="text-right">
                <div className={`font-mono font-semibold ${entry.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                  {entry.pnl >= 0 ? '+' : ''}${entry.pnl}
                </div>
                <div className="flex items-center gap-1 text-xs text-text-muted mt-0.5">
                  <Calendar className="w-3 h-3" />
                  {entry.date}
                </div>
              </div>
            </div>

            <p className="text-text-secondary text-sm mt-2">{entry.notes}</p>

            <div className="flex items-center gap-6 mt-3 text-xs text-text-muted">
              <span>Entry <span className="text-text-secondary font-mono">${entry.entryPrice.toFixed(2)}</span></span>
              <span>Exit <span className="text-text-secondary font-mono">${entry.exitPrice.toFixed(2)}</span></span>
              <span>Held <span className="text-text-secondary">{entry.holdDays}d</span></span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
