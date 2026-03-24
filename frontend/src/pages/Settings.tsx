import { useState } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw, Sliders, BrainCircuit, Bell, Shield, Eye, EyeOff } from 'lucide-react';

interface RegimeThresholds {
  riskOn: number;
  neutral: [number, number];
  riskOff: number;
}

interface SettingsState {
  regime: RegimeThresholds;
  aiPrompt: string;
  notifications: {
    confluenceAlerts: boolean;
    tradeSignals: boolean;
    morningBrief: boolean;
    riskAlerts: boolean;
  };
  riskLimits: {
    maxPositionSize: number;
    maxPortfolioBeta: number;
    maxSectorWeight: number;
    maxDailyLoss: number;
  };
}

const defaultSettings: SettingsState = {
  regime: { riskOn: 70, neutral: [40, 70], riskOff: 40 },
  aiPrompt: `You are a trading assistant specialized in ASX equities. Analyze the given symbol using technical analysis (RSI, MACD, moving averages, volume), fundamental data (earnings, PE ratio, sector strength), and market sentiment. Provide:
1. A directional bias (LONG/SHORT/NEUTRAL)
2. Key support and resistance levels
3. Confluence score (0-100)
4. Risk/reward assessment
5. Recommended position sizing

Consider the current market regime and correlation with existing portfolio positions. Flag any concentration or correlation risks.`,
  notifications: {
    confluenceAlerts: true,
    tradeSignals: true,
    morningBrief: true,
    riskAlerts: true,
  },
  riskLimits: {
    maxPositionSize: 5,
    maxPortfolioBeta: 1.5,
    maxSectorWeight: 30,
    maxDailyLoss: 2,
  },
};

export default function Settings() {
  const [settings, setSettings] = useState(defaultSettings);
  const [showPrompt, setShowPrompt] = useState(false);
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="space-y-5 max-w-4xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SettingsIcon className="w-5 h-5 text-text-secondary" />
          <h1 className="text-lg font-semibold text-text-primary">Settings</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSettings(defaultSettings)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-text-secondary hover:bg-bg-elevated rounded-lg text-sm transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-1.5 px-4 py-1.5 bg-accent-green text-bg-base rounded-lg text-sm font-semibold hover:brightness-110 transition"
          >
            <Save className="w-4 h-4" />
            {saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {/* Regime thresholds */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Sliders className="w-4 h-4 text-accent-amber" />
          <h3 className="text-sm font-semibold text-text-primary">Regime Thresholds</h3>
        </div>
        <p className="text-text-secondary text-xs mb-4">
          Configure the score ranges that determine market regime classification.
        </p>
        <div className="grid grid-cols-3 gap-6">
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Risk-Off (below)</label>
            <input
              type="number"
              value={settings.regime.riskOff}
              onChange={(e) => setSettings({ ...settings, regime: { ...settings.regime, riskOff: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-amber/50 focus:ring-1 focus:ring-accent-amber/20 transition"
            />
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent-red" />
              <span className="text-xs text-text-muted">Score 0 - {settings.regime.riskOff}</span>
            </div>
          </div>
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Neutral (range)</label>
            <div className="flex items-center gap-2">
              <input
                type="number"
                value={settings.regime.neutral[0]}
                onChange={(e) => setSettings({ ...settings, regime: { ...settings.regime, neutral: [Number(e.target.value), settings.regime.neutral[1]] } })}
                className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-amber/50 focus:ring-1 focus:ring-accent-amber/20 transition"
              />
              <span className="text-text-muted">-</span>
              <input
                type="number"
                value={settings.regime.neutral[1]}
                onChange={(e) => setSettings({ ...settings, regime: { ...settings.regime, neutral: [settings.regime.neutral[0], Number(e.target.value)] } })}
                className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-amber/50 focus:ring-1 focus:ring-accent-amber/20 transition"
              />
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent-amber" />
              <span className="text-xs text-text-muted">Score {settings.regime.neutral[0]} - {settings.regime.neutral[1]}</span>
            </div>
          </div>
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Risk-On (above)</label>
            <input
              type="number"
              value={settings.regime.riskOn}
              onChange={(e) => setSettings({ ...settings, regime: { ...settings.regime, riskOn: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-amber/50 focus:ring-1 focus:ring-accent-amber/20 transition"
            />
            <div className="mt-1.5 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent-green" />
              <span className="text-xs text-text-muted">Score {settings.regime.riskOn} - 100</span>
            </div>
          </div>
        </div>

        {/* Visual bar */}
        <div className="mt-4 h-3 rounded-full overflow-hidden flex">
          <div className="bg-accent-red/60" style={{ width: `${settings.regime.riskOff}%` }} />
          <div className="bg-accent-amber/60" style={{ width: `${settings.regime.neutral[1] - settings.regime.neutral[0]}%` }} />
          <div className="bg-accent-green/60" style={{ width: `${100 - settings.regime.riskOn}%` }} />
        </div>
      </div>

      {/* Risk limits */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Shield className="w-4 h-4 text-accent-red" />
          <h3 className="text-sm font-semibold text-text-primary">Risk Limits</h3>
        </div>
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Max Position Size (%)</label>
            <input
              type="number"
              value={settings.riskLimits.maxPositionSize}
              onChange={(e) => setSettings({ ...settings, riskLimits: { ...settings.riskLimits, maxPositionSize: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-red/50 focus:ring-1 focus:ring-accent-red/20 transition"
            />
          </div>
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Max Portfolio Beta</label>
            <input
              type="number"
              step="0.1"
              value={settings.riskLimits.maxPortfolioBeta}
              onChange={(e) => setSettings({ ...settings, riskLimits: { ...settings.riskLimits, maxPortfolioBeta: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-red/50 focus:ring-1 focus:ring-accent-red/20 transition"
            />
          </div>
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Max Sector Weight (%)</label>
            <input
              type="number"
              value={settings.riskLimits.maxSectorWeight}
              onChange={(e) => setSettings({ ...settings, riskLimits: { ...settings.riskLimits, maxSectorWeight: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-red/50 focus:ring-1 focus:ring-accent-red/20 transition"
            />
          </div>
          <div>
            <label className="block text-text-secondary text-xs mb-1.5">Max Daily Loss (%)</label>
            <input
              type="number"
              step="0.5"
              value={settings.riskLimits.maxDailyLoss}
              onChange={(e) => setSettings({ ...settings, riskLimits: { ...settings.riskLimits, maxDailyLoss: Number(e.target.value) } })}
              className="w-full bg-bg-base border border-border rounded-lg px-3 py-2 text-sm text-text-primary font-mono focus:outline-none focus:border-accent-red/50 focus:ring-1 focus:ring-accent-red/20 transition"
            />
          </div>
        </div>
      </div>

      {/* AI Prompt */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-accent-purple" />
            <h3 className="text-sm font-semibold text-text-primary">AI Analysis Prompt</h3>
          </div>
          <button
            onClick={() => setShowPrompt(!showPrompt)}
            className="flex items-center gap-1.5 text-xs text-text-secondary hover:text-text-primary transition-colors"
          >
            {showPrompt ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            {showPrompt ? 'Hide' : 'Show'} Prompt
          </button>
        </div>
        {showPrompt && (
          <textarea
            value={settings.aiPrompt}
            onChange={(e) => setSettings({ ...settings, aiPrompt: e.target.value })}
            rows={10}
            className="w-full bg-bg-base border border-border rounded-lg px-3 py-2.5 text-sm text-text-primary font-mono leading-relaxed placeholder:text-text-muted focus:outline-none focus:border-accent-purple/50 focus:ring-1 focus:ring-accent-purple/20 transition resize-y"
          />
        )}
        {!showPrompt && (
          <div className="bg-bg-base rounded-lg px-3 py-2.5 text-sm text-text-muted">
            Prompt hidden. Click &quot;Show Prompt&quot; to view and edit.
          </div>
        )}
      </div>

      {/* Notifications */}
      <div className="bg-bg-surface border border-border rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Bell className="w-4 h-4 text-accent-cyan" />
          <h3 className="text-sm font-semibold text-text-primary">Notifications</h3>
        </div>
        <div className="space-y-3">
          {Object.entries(settings.notifications).map(([key, enabled]) => {
            const labels: Record<string, string> = {
              confluenceAlerts: 'Confluence Alerts',
              tradeSignals: 'Trade Signals',
              morningBrief: 'Morning Brief',
              riskAlerts: 'Risk Alerts',
            };
            return (
              <label key={key} className="flex items-center justify-between cursor-pointer group">
                <span className="text-sm text-text-secondary group-hover:text-text-primary transition-colors">{labels[key]}</span>
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={() =>
                      setSettings({
                        ...settings,
                        notifications: { ...settings.notifications, [key]: !enabled },
                      })
                    }
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-bg-elevated rounded-full peer-checked:bg-accent-green/30 transition-colors" />
                  <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-text-muted rounded-full peer-checked:translate-x-4 peer-checked:bg-accent-green transition-all" />
                </div>
              </label>
            );
          })}
        </div>
      </div>
    </div>
  );
}
