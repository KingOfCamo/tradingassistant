# AI Trading Assistant v2.0

Human-in-the-loop intelligence system for ASX and US equity markets.

**You make every trade decision.** The AI does the research, pattern recognition, and alerting.

## What This Is

A personal trading intelligence platform that:

- Scans ASX 200, S&P 500, and NASDAQ 100 continuously
- Runs **9 quantitative strategies** in parallel
- Fuses signals via a **confluence engine** (multi-strategy agreement)
- Enriches ideas with personalised **Claude AI analysis**
- Detects **market regime** and gates strategies appropriately
- Tracks your **portfolio heat map** (beta, sector concentration, correlation)
- Delivers a **position-aware morning brief** before each market open
- Learns your decision patterns through **active capture**
- Maintains your trade journal with **CGT tax records**

## What This Is NOT

- Not an autonomous trading bot — zero orders are ever placed
- Not financial advice — personal research tool only
- Not connected to your broker — you trade manually in CMC Markets

## Architecture

```
Three-layer security:
  Layer 1: Cloudflare Tunnel + Zero Trust Access (no open ports)
  Layer 2: JWT auth (8hr access + 30d refresh with rotation)
  Layer 3: Backend hardening (rate limiting, audit logging, security headers)

Stack:
  Backend:  Python 3.9+ / FastAPI / PostgreSQL / Redis
  Frontend: React 18 / TypeScript / Vite / TailwindCSS
  AI:       Claude API (adaptive personalised prompts)
  Infra:    Docker Compose / Nginx / Cloudflare Tunnel
```

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A Cloudflare account (free) with a domain
- Anthropic API key

### Setup

1. **Clone and configure:**
   ```bash
   git clone https://github.com/KingOfCamo/tradingassistant.git
   cd tradingassistant
   cp .env.example .env
   ```

2. **Edit `.env`** with your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   FINNHUB_API_KEY=...
   SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
   ```

3. **Set up Cloudflare Tunnel** (see `infrastructure/cloudflare/SETUP.md`)

4. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

5. **Create your user:**
   ```bash
   docker-compose exec backend python -m backend.scripts.create_user
   ```

6. **Access the dashboard:**
   - Visit `https://trading.yourdomain.com`
   - Cloudflare Access login (email OTP)
   - App login (username/password)

### Local Development (without Docker)

```bash
# Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# Start PostgreSQL and Redis locally
uvicorn backend.api.app:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Broker: CMC Markets

Single broker for everything. The system models CMC's cost structure:

| Trade Type | Cost |
|---|---|
| AU stocks >= $1,000 AUD | $0 brokerage |
| AU stocks < $1,000 AUD | $9.90 flat |
| US stocks | $0 brokerage, ~0.65% FX spread each way |

Core ETF holdings (monitored, never traded by the system):
- **VAS.AX** — Vanguard Australian Shares ETF
- **IHVV.AX** — iShares S&P 500 AUD Hedged ETF

## The Nine Strategies

| # | Strategy | Type | Weight | Best Regime |
|---|---|---|---|---|
| 1 | Dual Momentum | Momentum | 1.5 | Strong/Moderate Bull |
| 2 | Trend Following | Momentum | 1.3 | Strong/Moderate Bull |
| 3 | Breakout | Momentum | 1.2 | Strong/Moderate Bull |
| 4 | Bollinger RSI | Mean Reversion | 1.0 | Choppy/Moderate |
| 5 | Pairs Scanner | Mean Reversion | 0.8 | Choppy/Risk-Off |
| 6 | Gap Fade | Mean Reversion | 0.7 | Moderate/Choppy |
| 7 | Fundamental Screen | Value | 1.4 | All regimes |
| 8 | Earnings Catalyst | Event | 1.1 | Bull regimes |
| 9 | Sector Rotation | Macro | 1.2 | All regimes |

## Market Regime Detection

The system classifies markets into 5 states and gates strategies:

- **Strong Trend Bull**: Momentum strategies active, mean reversion suppressed
- **Moderate Trend Bull**: All 9 strategies active (default)
- **Choppy Range Bound**: Mean reversion active, momentum suppressed
- **Risk-Off Elevated Fear**: Only fundamentals + pairs + rotation
- **Crisis Extreme Fear**: Only fundamental screen (HIGH conviction only)

## Confluence Engine

When 3+ strategies independently agree on the same stock, it's a **Confluence Alert** — the strongest signal the system produces. Tier 3+ alerts bypass the daily AI analysis budget and get immediate attention.

## How to Log a Trade

1. Place your trade in CMC Markets
2. In the dashboard: Portfolio → Log Position
3. Enter: symbol, shares, entry price, stop, targets
4. The system tracks it from there (P&L, alerts, morning brief)

## Tax Records

The Journal page maintains your CGT record:
- Entry/exit dates and prices
- Brokerage and FX costs
- Holding period (12-month CGT discount tracking)
- Export to CSV for your accountant

## Security

See `infrastructure/cloudflare/SETUP.md` for full security setup.

**Critical**: Never commit `.env` to git. The `.gitignore` prevents this, but verify with `git status` before every commit.

If your tunnel token is compromised: Cloudflare Zero Trust → Tunnels → Revoke immediately.

## Disclaimer

Personal research tool. Not financial product advice under the Corporations Act 2001. Do not share output as advice to others. All trading involves risk. Past backtest performance does not guarantee future results.
