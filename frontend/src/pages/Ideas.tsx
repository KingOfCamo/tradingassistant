import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Lightbulb,
  Filter,
  ArrowUpRight,
  ArrowDownRight,
  Clock,
  CheckCircle2,
  XCircle,
  Eye,
} from 'lucide-react';
import { getToken } from '../hooks/useAuth.ts';

type IdeaStatus = 'active' | 'triggered' | 'passed' | 'expired';

interface Idea {
  id: string;
  symbol: string;
  direction: 'LONG' | 'SHORT';
  strategy: string;
  confluenceScore: number;
  regime: string;
  status: IdeaStatus;
  entryPrice: number;
  targetPrice: number;
  stopLoss: number;
  createdAt: string;
  notes: string;
}

const statusConfig: Record<IdeaStatus, { label: string; color: string; icon: typeof Clock }> = {
  active: { label: 'Active', color: 'bg-accent-green/10 text-accent-green', icon: Eye },
  triggered: { label: 'Triggered', color: 'bg-accent-blue/10 text-accent-blue', icon: CheckCircle2 },
  passed: { label: 'Passed', color: 'bg-text-muted/15 text-text-muted', icon: XCircle },
  expired: { label: 'Expired', color: 'bg-accent-amber/10 text-accent-amber', icon: Clock },
};

const placeholderIdeas: Idea[] = [
  { id: '1', symbol: 'FMG', direction: 'LONG', strategy: 'Momentum', confluenceScore: 85, regime: 'Risk-On', status: 'active', entryPrice: 19.80, targetPrice: 22.40, stopLoss: 18.90, createdAt: '2024-03-24T08:30:00Z', notes: 'Iron ore breakout above 200d MA, volume confirmation' },
  { id: '2', symbol: 'CSL', direction: 'LONG', strategy: 'Mean Reversion', confluenceScore: 72, regime: 'Neutral', status: 'active', entryPrice: 282.00, targetPrice: 295.00, stopLoss: 275.00, createdAt: '2024-03-24T09:15:00Z', notes: 'Oversold bounce at key support, RSI divergence' },
  { id: '3', symbol: 'WOW', direction: 'SHORT', strategy: 'Breakdown', confluenceScore: 68, regime: 'Neutral', status: 'triggered', entryPrice: 31.50, targetPrice: 28.80, stopLoss: 32.80, createdAt: '2024-03-23T14:00:00Z', notes: 'Head and shoulders completion, weak consumer data' },
  { id: '4', symbol: 'ALL', direction: 'LONG', strategy: 'Breakout', confluenceScore: 61, regime: 'Risk-On', status: 'passed', entryPrice: 46.00, targetPrice: 50.50, stopLoss: 44.20, createdAt: '2024-03-22T10:00:00Z', notes: 'Gaming revenue beat, ascending triangle' },
  { id: '5', symbol: 'STO', direction: 'SHORT', strategy: 'Momentum', confluenceScore: 55, regime: 'Risk-Off', status: 'expired', entryPrice: 7.20, targetPrice: 6.40, stopLoss: 7.60, createdAt: '2024-03-21T11:30:00Z', notes: 'Oil weakness, distribution pattern' },
];

async function fetchIdeas(): Promise<Idea[]> {
  const token = getToken();
  const res = await fetch('/api/ideas', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed to load ideas');
  return res.json() as Promise<Idea[]>;
}

const statuses: IdeaStatus[] = ['active', 'triggered', 'passed', 'expired'];

export default function Ideas() {
  const [filterStatus, setFilterStatus] = useState<IdeaStatus | 'all'>('all');

  const { data } = useQuery({
    queryKey: ['ideas'],
    queryFn: fetchIdeas,
    placeholderData: placeholderIdeas,
  });

  const ideas = data ?? placeholderIdeas;
  const filtered = filterStatus === 'all' ? ideas : ideas.filter((i) => i.status === filterStatus);

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-accent-purple" />
          <h1 className="text-lg font-semibold text-text-primary">Ideas Feed</h1>
          <span className="text-xs text-text-muted bg-bg-elevated px-2 py-0.5 rounded-full ml-1">
            {ideas.length} total
          </span>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2">
        <Filter className="w-4 h-4 text-text-muted" />
        <button
          onClick={() => setFilterStatus('all')}
          className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            filterStatus === 'all' ? 'bg-accent-blue/15 text-accent-blue' : 'text-text-secondary hover:bg-bg-elevated'
          }`}
        >
          All
        </button>
        {statuses.map((s) => {
          const cfg = statusConfig[s];
          return (
            <button
              key={s}
              onClick={() => setFilterStatus(s)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filterStatus === s ? cfg.color : 'text-text-secondary hover:bg-bg-elevated'
              }`}
            >
              {cfg.label}
            </button>
          );
        })}
      </div>

      {/* Ideas grid */}
      <div className="grid grid-cols-1 gap-3">
        {filtered.map((idea) => {
          const cfg = statusConfig[idea.status];
          const StatusIcon = cfg.icon;
          return (
            <div key={idea.id} className="bg-bg-surface border border-border rounded-xl p-4 hover:border-border/80 transition-colors">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-text-primary font-semibold">{idea.symbol}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      idea.direction === 'LONG' ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/10 text-accent-red'
                    }`}>
                      {idea.direction === 'LONG' ? (
                        <span className="inline-flex items-center gap-1"><ArrowUpRight className="w-3 h-3" />LONG</span>
                      ) : (
                        <span className="inline-flex items-center gap-1"><ArrowDownRight className="w-3 h-3" />SHORT</span>
                      )}
                    </span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded bg-accent-purple/10 text-accent-purple">{idea.strategy}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-accent-cyan/10 text-accent-cyan">{idea.regime}</span>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <div className="w-9 h-9 rounded-full border-2 border-accent-blue flex items-center justify-center">
                      <span className="text-xs font-bold text-accent-blue">{idea.confluenceScore}</span>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-1 rounded ${cfg.color}`}>
                    <StatusIcon className="w-3 h-3" />
                    {cfg.label}
                  </span>
                </div>
              </div>

              <p className="text-text-secondary text-sm mt-2">{idea.notes}</p>

              <div className="flex items-center gap-6 mt-3 text-xs text-text-muted">
                <span>Entry <span className="text-text-secondary font-mono">${idea.entryPrice.toFixed(2)}</span></span>
                <span>Target <span className="text-accent-green font-mono">${idea.targetPrice.toFixed(2)}</span></span>
                <span>Stop <span className="text-accent-red font-mono">${idea.stopLoss.toFixed(2)}</span></span>
                <span className="ml-auto">{new Date(idea.createdAt).toLocaleDateString()}</span>
              </div>
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="bg-bg-surface border border-border rounded-xl p-12 text-center">
          <Lightbulb className="w-8 h-8 text-text-muted mx-auto mb-3" />
          <p className="text-text-secondary">No ideas match the selected filter</p>
        </div>
      )}
    </div>
  );
}
