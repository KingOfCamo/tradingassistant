import { useQuery } from '@tanstack/react-query';
import { Activity, Wifi, WifiOff, Clock } from 'lucide-react';
import { format } from 'date-fns';
import { getToken } from '../hooks/useAuth.ts';

interface MarketStatus {
  exchange: string;
  status: 'open' | 'closed' | 'pre' | 'post';
}

interface RegimeData {
  label: string;
  color: 'green' | 'amber' | 'red';
}

interface TopBarData {
  markets: MarketStatus[];
  regime: RegimeData;
  audUsd: number;
  wsConnected: boolean;
}

const statusColors: Record<string, string> = {
  open: 'bg-accent-green/15 text-accent-green',
  closed: 'bg-text-muted/15 text-text-muted',
  pre: 'bg-accent-amber/15 text-accent-amber',
  post: 'bg-accent-blue/15 text-accent-blue',
};

const regimeColors: Record<string, string> = {
  green: 'bg-accent-green/15 text-accent-green',
  amber: 'bg-accent-amber/15 text-accent-amber',
  red: 'bg-accent-red/15 text-accent-red',
};

async function fetchTopBarData(): Promise<TopBarData> {
  const token = getToken();
  const res = await fetch('/api/market/status', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed to fetch market status');
  return res.json() as Promise<TopBarData>;
}

// Fallback data shown before API responds
const fallback: TopBarData = {
  markets: [
    { exchange: 'ASX', status: 'closed' },
    { exchange: 'NYSE', status: 'closed' },
    { exchange: 'NASDAQ', status: 'closed' },
  ],
  regime: { label: 'Neutral', color: 'amber' },
  audUsd: 0.6485,
  wsConnected: false,
};

export function TopBar() {
  const { data } = useQuery({
    queryKey: ['market-status'],
    queryFn: fetchTopBarData,
    refetchInterval: 30_000,
    placeholderData: fallback,
  });

  const bar = data ?? fallback;
  const now = format(new Date(), 'EEE d MMM, HH:mm');

  return (
    <header className="h-12 bg-bg-surface border-b border-border flex items-center justify-between px-5 shrink-0">
      {/* Left: Market pills */}
      <div className="flex items-center gap-2">
        {bar.markets.map((m) => (
          <span
            key={m.exchange}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${statusColors[m.status] ?? statusColors.closed}`}
          >
            <span className="w-1.5 h-1.5 rounded-full bg-current" />
            {m.exchange}
          </span>
        ))}

        {/* Regime pill */}
        <span
          className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ml-2 ${regimeColors[bar.regime.color] ?? regimeColors.amber}`}
        >
          <Activity className="w-3 h-3" />
          {bar.regime.label}
        </span>
      </div>

      {/* Right: AUD/USD, connection, clock */}
      <div className="flex items-center gap-4 text-sm">
        <span className="text-text-secondary">
          AUD/USD{' '}
          <span className="text-text-primary font-mono font-medium">
            {bar.audUsd.toFixed(4)}
          </span>
        </span>

        <span className="flex items-center gap-1 text-xs">
          {bar.wsConnected ? (
            <Wifi className="w-3.5 h-3.5 text-accent-green" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-text-muted" />
          )}
        </span>

        <span className="flex items-center gap-1.5 text-text-secondary text-xs">
          <Clock className="w-3.5 h-3.5" />
          {now}
        </span>
      </div>
    </header>
  );
}
