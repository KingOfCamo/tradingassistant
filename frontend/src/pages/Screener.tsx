import { useState } from 'react';
import { Search, SlidersHorizontal, ArrowUpDown, ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface ScreenerRow {
  symbol: string;
  name: string;
  price: number;
  change: number;
  changePct: number;
  volume: string;
  marketCap: string;
  rsi: number;
  sector: string;
  signal: string;
}

const placeholderRows: ScreenerRow[] = [
  { symbol: 'BHP', name: 'BHP Group', price: 45.80, change: 0.85, changePct: 1.89, volume: '12.4M', marketCap: '$232B', rsi: 58, sector: 'Materials', signal: 'Bullish' },
  { symbol: 'CBA', name: 'Commonwealth Bank', price: 110.85, change: -1.45, changePct: -1.29, volume: '4.2M', marketCap: '$188B', rsi: 42, sector: 'Financials', signal: 'Neutral' },
  { symbol: 'FMG', name: 'Fortescue', price: 19.80, change: 0.62, changePct: 3.23, volume: '18.7M', marketCap: '$60B', rsi: 71, sector: 'Materials', signal: 'Bullish' },
  { symbol: 'CSL', name: 'CSL Limited', price: 282.00, change: -3.20, changePct: -1.12, volume: '1.1M', marketCap: '$135B', rsi: 35, sector: 'Healthcare', signal: 'Oversold' },
  { symbol: 'WDS', name: 'Woodside Energy', price: 26.90, change: -0.70, changePct: -2.54, volume: '6.8M', marketCap: '$50B', rsi: 38, sector: 'Energy', signal: 'Bearish' },
  { symbol: 'RIO', name: 'Rio Tinto', price: 118.50, change: 2.10, changePct: 1.81, volume: '3.5M', marketCap: '$78B', rsi: 62, sector: 'Materials', signal: 'Bullish' },
  { symbol: 'WOW', name: 'Woolworths', price: 31.50, change: -0.42, changePct: -1.32, volume: '5.3M', marketCap: '$39B', rsi: 44, sector: 'Consumer', signal: 'Bearish' },
  { symbol: 'NAB', name: 'National Australia Bank', price: 37.20, change: 0.15, changePct: 0.40, volume: '7.1M', marketCap: '$115B', rsi: 51, sector: 'Financials', signal: 'Neutral' },
];

function rsiColor(rsi: number) {
  if (rsi >= 70) return 'text-accent-red';
  if (rsi <= 30) return 'text-accent-green';
  return 'text-text-secondary';
}

function signalStyle(signal: string) {
  switch (signal) {
    case 'Bullish': return 'bg-accent-green/10 text-accent-green';
    case 'Bearish': return 'bg-accent-red/10 text-accent-red';
    case 'Oversold': return 'bg-accent-amber/10 text-accent-amber';
    default: return 'bg-text-muted/15 text-text-muted';
  }
}

export default function Screener() {
  const [query, setQuery] = useState('');
  const [sectorFilter, setSectorFilter] = useState('All');

  const sectors = ['All', ...new Set(placeholderRows.map((r) => r.sector))];
  const filtered = placeholderRows.filter((r) => {
    const matchesQuery = !query || r.symbol.toLowerCase().includes(query.toLowerCase()) || r.name.toLowerCase().includes(query.toLowerCase());
    const matchesSector = sectorFilter === 'All' || r.sector === sectorFilter;
    return matchesQuery && matchesSector;
  });

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-2">
        <Search className="w-5 h-5 text-accent-cyan" />
        <h1 className="text-lg font-semibold text-text-primary">Screener</h1>
      </div>

      {/* Filters */}
      <div className="bg-bg-surface border border-border rounded-xl p-4">
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 text-text-muted absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search symbol or name..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full bg-bg-base border border-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-cyan/50 focus:ring-1 focus:ring-accent-cyan/20 transition"
            />
          </div>
          <div className="flex items-center gap-2">
            <SlidersHorizontal className="w-4 h-4 text-text-muted" />
            {sectors.map((s) => (
              <button
                key={s}
                onClick={() => setSectorFilter(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  sectorFilter === s ? 'bg-accent-cyan/15 text-accent-cyan' : 'text-text-secondary hover:bg-bg-elevated'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-bg-surface border border-border rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">
                <span className="inline-flex items-center gap-1">Symbol <ArrowUpDown className="w-3 h-3" /></span>
              </th>
              <th className="text-right px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Price</th>
              <th className="text-right px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Change</th>
              <th className="text-right px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Volume</th>
              <th className="text-right px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Mkt Cap</th>
              <th className="text-right px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">RSI</th>
              <th className="text-left px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Sector</th>
              <th className="text-left px-4 py-3 text-text-muted text-xs uppercase tracking-wider font-medium">Signal</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((r) => (
              <tr key={r.symbol} className="hover:bg-bg-elevated/50 transition-colors cursor-pointer">
                <td className="px-4 py-3">
                  <div>
                    <div className="font-semibold text-text-primary">{r.symbol}</div>
                    <div className="text-xs text-text-muted">{r.name}</div>
                  </div>
                </td>
                <td className="px-4 py-3 text-right font-mono text-text-primary">${r.price.toFixed(2)}</td>
                <td className="px-4 py-3 text-right">
                  <span className={`inline-flex items-center gap-1 font-mono ${r.change >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    {r.change >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                    {r.changePct >= 0 ? '+' : ''}{r.changePct.toFixed(2)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-text-secondary">{r.volume}</td>
                <td className="px-4 py-3 text-right text-text-secondary">{r.marketCap}</td>
                <td className={`px-4 py-3 text-right font-mono font-medium ${rsiColor(r.rsi)}`}>{r.rsi}</td>
                <td className="px-4 py-3 text-text-secondary">{r.sector}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${signalStyle(r.signal)}`}>{r.signal}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <div className="p-12 text-center text-text-muted text-sm">No results match your filters</div>
        )}
      </div>
    </div>
  );
}
