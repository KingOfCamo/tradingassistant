import { useQuery } from '@tanstack/react-query';
import { Layers, TrendingUp, ArrowUpRight, ArrowDownRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getToken } from '../hooks/useAuth.ts';

interface ConfluenceAlert {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  score: number;
  signals: string[];
  strategies: string[];
  timestamp: string;
}

const placeholderAlerts: ConfluenceAlert[] = [
  { id: '1', symbol: 'FMG', direction: 'LONG', score: 92, signals: ['RSI Oversold Bounce', 'Volume Spike', 'Above 200d MA', 'Sector Momentum'], strategies: ['Momentum', 'Breakout'], timestamp: '2024-03-24T08:00:00Z' },
  { id: '2', symbol: 'BHP', direction: 'LONG', score: 85, signals: ['Bullish Engulfing', 'Support Test', 'Commodity Tailwind'], strategies: ['Mean Reversion'], timestamp: '2024-03-24T08:15:00Z' },
  { id: '3', symbol: 'WOW', direction: 'SHORT', score: 78, signals: ['Head & Shoulders', 'Below 50d MA', 'Weak Consumer'], strategies: ['Breakdown'], timestamp: '2024-03-24T09:00:00Z' },
  { id: '4', symbol: 'CSL', direction: 'LONG', score: 72, signals: ['RSI Divergence', 'Support Hold'], strategies: ['Mean Reversion'], timestamp: '2024-03-24T09:30:00Z' },
  { id: '5', symbol: 'RIO', direction: 'LONG', score: 68, signals: ['Sector Rotation', 'Volume'], strategies: ['Momentum'], timestamp: '2024-03-24T10:00:00Z' },
  { id: '6', symbol: 'STO', direction: 'SHORT', score: 55, signals: ['Distribution', 'Oil Weakness'], strategies: ['Momentum'], timestamp: '2024-03-24T10:30:00Z' },
];

async function fetchAlerts(): Promise<ConfluenceAlert[]> {
  const token = getToken();
  const res = await fetch('/api/confluence', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed');
  return res.json() as Promise<ConfluenceAlert[]>;
}

function scoreColor(score: number) {
  if (score >= 80) return '#00C896';
  if (score >= 60) return '#F59E0B';
  return '#F04B5A';
}

export default function Confluence() {
  const { data } = useQuery({
    queryKey: ['confluence'],
    queryFn: fetchAlerts,
    placeholderData: placeholderAlerts,
  });

  const alerts = data ?? placeholderAlerts;
  const sorted = [...alerts].sort((a, b) => b.score - a.score);

  const chartData = sorted.map((a) => ({ name: a.symbol, score: a.score }));

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Layers className="w-5 h-5 text-accent-blue" />
        <h1 className="text-lg font-semibold text-text-primary">Confluence Alerts</h1>
        <span className="text-xs text-text-muted bg-bg-elevated px-2 py-0.5 rounded-full ml-1">{alerts.length} alerts</span>
      </div>

      {/* Score distribution chart */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-4">Score Distribution</h3>
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fill: '#8A9BB5', fontSize: 11 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: '#8A9BB5', fontSize: 11 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#8A9BB5' }}
                itemStyle={{ color: '#E2E8F0' }}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {chartData.map((entry, idx) => (
                  <Cell key={idx} fill={scoreColor(entry.score)} fillOpacity={0.8} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Alert cards */}
      <div className="space-y-3">
        {sorted.map((alert) => (
          <div key={alert.id} className="bg-bg-surface border border-border rounded-xl p-4 hover:border-border/80 transition-colors">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center font-bold text-sm"
                  style={{ background: `${scoreColor(alert.score)}15`, color: scoreColor(alert.score) }}
                >
                  {alert.score}
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-semibold">{alert.symbol}</span>
                    <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded ${
                      alert.direction === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'
                    }`}>
                      {alert.direction === 'LONG' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {alert.direction}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-1">
                    {alert.strategies.map((s) => (
                      <span key={s} className="text-xs px-2 py-0.5 rounded bg-accent-purple/10 text-accent-purple">{s}</span>
                    ))}
                  </div>
                </div>
              </div>

              <span className="text-xs text-text-muted">{new Date(alert.timestamp).toLocaleTimeString()}</span>
            </div>

            {/* Signals */}
            <div className="flex flex-wrap gap-2 mt-3">
              {alert.signals.map((sig) => (
                <span key={sig} className="inline-flex items-center gap-1 text-xs bg-bg-elevated text-text-secondary px-2.5 py-1 rounded-lg">
                  <TrendingUp className="w-3 h-3 text-accent-cyan" />
                  {sig}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
