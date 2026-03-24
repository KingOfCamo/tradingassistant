import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { BrainCircuit, Play, Loader2, Clock, ChevronDown, ChevronUp, Sparkles } from 'lucide-react';
import { getToken } from '../hooks/useAuth.ts';

interface AnalysisRun {
  id: string;
  symbol: string;
  type: 'technical' | 'fundamental' | 'sentiment' | 'composite';
  status: 'completed' | 'running' | 'queued';
  summary: string;
  signals: string[];
  recommendation: string;
  confidence: number;
  runAt: string;
}

const typeStyles: Record<string, string> = {
  technical: 'bg-accent-blue/10 text-accent-blue',
  fundamental: 'bg-accent-green/10 text-accent-green',
  sentiment: 'bg-accent-purple/10 text-accent-purple',
  composite: 'bg-accent-amber/10 text-accent-amber',
};

const placeholderRuns: AnalysisRun[] = [
  {
    id: '1', symbol: 'BHP', type: 'composite', status: 'completed',
    summary: 'Composite analysis shows strong bullish setup. Technical momentum aligning with fundamental commodity tailwinds. Sentiment skewing positive from institutional flows. Mean reversion signal from RSI confirms entry zone.',
    signals: ['RSI Oversold Bounce', 'Iron Ore +2.3%', 'Institutional Net Buying', 'Above 200d MA'],
    recommendation: 'LONG with high conviction', confidence: 85, runAt: '2024-03-24T08:00:00Z',
  },
  {
    id: '2', symbol: 'CSL', type: 'technical', status: 'completed',
    summary: 'Price testing major support at $275 with bullish divergence on RSI. Volume declining on selloff suggests exhaustion. MACD histogram turning positive. Watch for confirmation above $280.',
    signals: ['RSI Divergence', 'Support Test', 'Volume Exhaustion', 'MACD Cross'],
    recommendation: 'LONG on confirmation', confidence: 68, runAt: '2024-03-24T08:30:00Z',
  },
  {
    id: '3', symbol: 'WOW', type: 'sentiment', status: 'completed',
    summary: 'Consumer sentiment deteriorating. Short interest rising. Social media mentions trending negative after earnings guidance downgrade. Institutional positioning shift to underweight.',
    signals: ['Rising Short Interest', 'Negative Sentiment', 'Downgrade Cycle'],
    recommendation: 'SHORT bias, wait for technical trigger', confidence: 62, runAt: '2024-03-24T09:00:00Z',
  },
  {
    id: '4', symbol: 'FMG', type: 'fundamental', status: 'running',
    summary: '', signals: [], recommendation: '', confidence: 0, runAt: '2024-03-24T09:30:00Z',
  },
];

async function fetchAnalysis(): Promise<AnalysisRun[]> {
  const token = getToken();
  const res = await fetch('/api/analysis', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error('Failed');
  return res.json() as Promise<AnalysisRun[]>;
}

export default function Analysis() {
  const [expandedId, setExpandedId] = useState<string | null>('1');

  const { data } = useQuery({
    queryKey: ['analysis'],
    queryFn: fetchAnalysis,
    placeholderData: placeholderRuns,
  });

  const runs = data ?? placeholderRuns;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BrainCircuit className="w-5 h-5 text-accent-purple" />
          <h1 className="text-lg font-semibold text-text-primary">AI Analysis</h1>
        </div>
        <button className="flex items-center gap-1.5 px-3 py-1.5 bg-accent-purple/10 text-accent-purple rounded-lg text-sm font-medium hover:bg-accent-purple/20 transition-colors">
          <Play className="w-4 h-4" />
          Run Analysis
        </button>
      </div>

      {/* Quick run */}
      <div className="bg-bg-surface border border-border rounded-xl p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">Quick Analysis</h3>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Enter symbol (e.g. BHP)"
            className="flex-1 bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-accent-purple/50 focus:ring-1 focus:ring-accent-purple/20 transition"
          />
          <select className="bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-secondary focus:outline-none">
            <option value="composite">Composite</option>
            <option value="technical">Technical</option>
            <option value="fundamental">Fundamental</option>
            <option value="sentiment">Sentiment</option>
          </select>
          <button className="flex items-center gap-1.5 px-4 py-2 bg-accent-purple text-white rounded-lg text-sm font-semibold hover:brightness-110 transition">
            <Sparkles className="w-4 h-4" />
            Analyze
          </button>
        </div>
      </div>

      {/* Analysis runs */}
      <div className="space-y-3">
        {runs.map((run) => {
          const isExpanded = expandedId === run.id;
          return (
            <div key={run.id} className="bg-bg-surface border border-border rounded-xl overflow-hidden hover:border-border/80 transition-colors">
              {/* Header */}
              <button
                onClick={() => setExpandedId(isExpanded ? null : run.id)}
                className="w-full flex items-center justify-between px-5 py-4"
              >
                <div className="flex items-center gap-3">
                  <span className="text-text-primary font-semibold">{run.symbol}</span>
                  <span className={`text-xs font-medium px-2 py-0.5 rounded ${typeStyles[run.type]}`}>{run.type}</span>
                  {run.status === 'running' && (
                    <span className="inline-flex items-center gap-1 text-xs text-accent-amber">
                      <Loader2 className="w-3 h-3 animate-spin" /> Running
                    </span>
                  )}
                  {run.status === 'completed' && run.confidence > 0 && (
                    <span className="text-xs text-text-muted">
                      Confidence: <span className={`font-mono font-medium ${run.confidence >= 70 ? 'text-accent-green' : run.confidence >= 50 ? 'text-accent-amber' : 'text-accent-red'}`}>{run.confidence}%</span>
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1 text-xs text-text-muted">
                    <Clock className="w-3 h-3" />
                    {new Date(run.runAt).toLocaleTimeString()}
                  </span>
                  {isExpanded ? <ChevronUp className="w-4 h-4 text-text-muted" /> : <ChevronDown className="w-4 h-4 text-text-muted" />}
                </div>
              </button>

              {/* Expanded content */}
              {isExpanded && run.status === 'completed' && (
                <div className="border-t border-border px-5 py-4 space-y-4">
                  {/* Summary */}
                  <div>
                    <h4 className="text-xs text-text-muted uppercase tracking-wider font-medium mb-2">Summary</h4>
                    <p className="text-text-secondary text-sm leading-relaxed">{run.summary}</p>
                  </div>

                  {/* Signals */}
                  <div>
                    <h4 className="text-xs text-text-muted uppercase tracking-wider font-medium mb-2">Signals</h4>
                    <div className="flex flex-wrap gap-2">
                      {run.signals.map((sig) => (
                        <span key={sig} className="text-xs bg-bg-elevated text-text-secondary px-2.5 py-1 rounded-lg">{sig}</span>
                      ))}
                    </div>
                  </div>

                  {/* Recommendation */}
                  <div className="bg-bg-elevated rounded-lg p-3 flex items-center justify-between">
                    <div>
                      <h4 className="text-xs text-text-muted uppercase tracking-wider font-medium mb-1">Recommendation</h4>
                      <span className="text-sm font-semibold text-text-primary">{run.recommendation}</span>
                    </div>
                    <div className="w-12 h-12 rounded-full border-2 flex items-center justify-center" style={{ borderColor: run.confidence >= 70 ? '#00C896' : run.confidence >= 50 ? '#F59E0B' : '#F04B5A' }}>
                      <span className="text-sm font-bold" style={{ color: run.confidence >= 70 ? '#00C896' : run.confidence >= 50 ? '#F59E0B' : '#F04B5A' }}>{run.confidence}</span>
                    </div>
                  </div>
                </div>
              )}

              {isExpanded && run.status === 'running' && (
                <div className="border-t border-border px-5 py-8 flex flex-col items-center">
                  <Loader2 className="w-6 h-6 text-accent-purple animate-spin mb-2" />
                  <span className="text-sm text-text-secondary">Analysis in progress...</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
