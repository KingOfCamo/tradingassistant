import { ShieldAlert, AlertTriangle, TrendingUp, Gauge } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';

interface SectorWeight {
  sector: string;
  weight: number;
  beta: number;
  var95: number;
}

interface RiskMetrics {
  portfolioBeta: number;
  var95: number;
  maxDrawdown: number;
  sharpeRatio: number;
  concentrationRisk: number;
  correlationRisk: string;
}

const sectors: SectorWeight[] = [
  { sector: 'Materials', weight: 30.5, beta: 1.35, var95: 2.8 },
  { sector: 'Financials', weight: 11.2, beta: 1.1, var95: 1.9 },
  { sector: 'Healthcare', weight: 11.4, beta: 0.85, var95: 1.5 },
  { sector: 'Energy', weight: 8.1, beta: 1.45, var95: 3.1 },
  { sector: 'Consumer', weight: 0, beta: 0.9, var95: 1.4 },
  { sector: 'Technology', weight: 0, beta: 1.2, var95: 2.5 },
];

const metrics: RiskMetrics = {
  portfolioBeta: 1.18,
  var95: 2.4,
  maxDrawdown: -5.8,
  sharpeRatio: 1.42,
  concentrationRisk: 72,
  correlationRisk: 'Medium',
};

const activeSectors = sectors.filter((s) => s.weight > 0);

function betaColor(beta: number) {
  if (beta > 1.3) return '#F04B5A';
  if (beta > 1.0) return '#F59E0B';
  return '#00C896';
}

function riskLevel(val: number, thresholds: [number, number]): { label: string; color: string } {
  if (val > thresholds[1]) return { label: 'High', color: 'text-accent-red' };
  if (val > thresholds[0]) return { label: 'Medium', color: 'text-accent-amber' };
  return { label: 'Low', color: 'text-accent-green' };
}

export default function RiskMap() {
  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-2">
        <ShieldAlert className="w-5 h-5 text-accent-red" />
        <h1 className="text-lg font-semibold text-text-primary">Risk Map</h1>
      </div>

      {/* Risk metric cards */}
      <div className="grid grid-cols-6 gap-4">
        <RiskCard label="Portfolio Beta" value={metrics.portfolioBeta.toFixed(2)} risk={riskLevel(metrics.portfolioBeta, [1.0, 1.3])} />
        <RiskCard label="VaR (95%)" value={`${metrics.var95}%`} risk={riskLevel(metrics.var95, [2.0, 3.0])} />
        <RiskCard label="Max Drawdown" value={`${metrics.maxDrawdown}%`} risk={riskLevel(Math.abs(metrics.maxDrawdown), [5, 10])} />
        <RiskCard label="Sharpe Ratio" value={metrics.sharpeRatio.toFixed(2)} risk={{ label: metrics.sharpeRatio >= 1 ? 'Good' : 'Low', color: metrics.sharpeRatio >= 1 ? 'text-accent-green' : 'text-accent-red' }} />
        <RiskCard label="Concentration" value={`${metrics.concentrationRisk}%`} risk={riskLevel(metrics.concentrationRisk, [50, 75])} />
        <RiskCard label="Correlation" value={metrics.correlationRisk} risk={riskLevel(metrics.correlationRisk === 'High' ? 80 : metrics.correlationRisk === 'Medium' ? 55 : 20, [40, 70])} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Sector weight heat map */}
        <div className="bg-bg-surface border border-border rounded-xl p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-4">Sector Weights</h3>
          <div className="space-y-2">
            {sectors.map((s) => (
              <div key={s.sector} className="flex items-center gap-3">
                <span className="text-text-secondary text-xs w-24 shrink-0">{s.sector}</span>
                <div className="flex-1 bg-bg-base rounded-full h-6 overflow-hidden relative">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${Math.max(s.weight, 0)}%`,
                      background: s.weight > 25 ? '#F04B5A' : s.weight > 15 ? '#F59E0B' : '#00C896',
                      opacity: s.weight === 0 ? 0.2 : 0.7,
                    }}
                  />
                  {s.weight > 0 && (
                    <span className="absolute right-2 top-1/2 -translate-y-1/2 text-xs font-mono text-text-primary">
                      {s.weight.toFixed(1)}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
          {activeSectors.some((s) => s.weight > 25) && (
            <div className="flex items-center gap-2 mt-4 bg-accent-red/10 border border-accent-red/20 rounded-lg px-3 py-2 text-xs text-accent-red">
              <AlertTriangle className="w-3.5 h-3.5" />
              Concentration risk: sector weight exceeds 25%
            </div>
          )}
        </div>

        {/* Beta gauge per sector */}
        <div className="bg-bg-surface border border-border rounded-xl p-5">
          <div className="flex items-center gap-2 mb-4">
            <Gauge className="w-4 h-4 text-accent-amber" />
            <h3 className="text-sm font-semibold text-text-primary">Beta by Sector</h3>
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={activeSectors} layout="vertical">
                <XAxis type="number" domain={[0, 2]} tick={{ fill: '#8A9BB5', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="sector" tick={{ fill: '#8A9BB5', fontSize: 11 }} width={80} axisLine={false} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#131E38', border: '1px solid #1E2D4A', borderRadius: 8, fontSize: 12 }}
                  formatter={(v) => [Number(v).toFixed(2), 'Beta']}
                />
                <Bar dataKey="beta" radius={[0, 4, 4, 0]} barSize={20}>
                  {activeSectors.map((s, i) => (
                    <Cell key={i} fill={betaColor(s.beta)} fillOpacity={0.8} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          {/* Beta reference */}
          <div className="flex items-center gap-4 mt-3 text-xs text-text-muted">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-green" /> &lt; 1.0</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-amber" /> 1.0 - 1.3</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-accent-red" /> &gt; 1.3</span>
          </div>
        </div>
      </div>

      {/* VaR breakdown */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <TrendingUp className="w-4 h-4 text-accent-purple" />
          <h3 className="text-sm font-semibold text-text-primary">Value at Risk by Sector</h3>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-text-muted text-xs uppercase tracking-wider">
              <th className="text-left pb-3 font-medium">Sector</th>
              <th className="text-right pb-3 font-medium">Weight</th>
              <th className="text-right pb-3 font-medium">Beta</th>
              <th className="text-right pb-3 font-medium">VaR (95%)</th>
              <th className="text-left pb-3 pl-4 font-medium">Risk</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {activeSectors.map((s) => {
              const risk = riskLevel(s.var95, [2.0, 3.0]);
              return (
                <tr key={s.sector} className="hover:bg-bg-elevated/30 transition-colors">
                  <td className="py-2.5 font-medium text-text-primary">{s.sector}</td>
                  <td className="py-2.5 text-right text-text-secondary font-mono">{s.weight.toFixed(1)}%</td>
                  <td className="py-2.5 text-right font-mono" style={{ color: betaColor(s.beta) }}>{s.beta.toFixed(2)}</td>
                  <td className="py-2.5 text-right text-text-secondary font-mono">{s.var95}%</td>
                  <td className="py-2.5 pl-4">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${risk.color.replace('text-', 'bg-').replace('accent-', 'accent-')}/10 ${risk.color}`}>
                      {risk.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RiskCard({ label, value, risk }: { label: string; value: string; risk: { label: string; color: string } }) {
  return (
    <div className="bg-bg-surface border border-border rounded-xl p-4">
      <div className="text-text-muted text-xs uppercase tracking-wider font-medium mb-2">{label}</div>
      <div className="text-lg font-bold font-mono text-text-primary">{value}</div>
      <div className={`text-xs font-medium mt-1 ${risk.color}`}>{risk.label}</div>
    </div>
  );
}
