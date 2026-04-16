# Macro Tracker

A simple single-page macro situation dashboard. Python script pulls daily market data (FX, rates, equities, commodities, energy, crypto) and a static HTML file renders it with a risk-on/off signal scorecard at the top.

No backend server, no build step, no external JS/CSS dependencies. Just Python + HTML.

![Dashboard](docs/screenshots/dashboard-desktop.png)

## What it tracks

**Signal scorecard (hero)** — quick read on macro risk appetite:

| Signal | Clear when | Rationale |
|--------|------------|-----------|
| VIX | `< 20` | Volatility subsiding, market confident |
| DXY | `< 98` | USD weakening, capital flowing to EM |
| UST 2Y | `< 3.50%` | Market pricing rate cuts, liquidity incoming |
| BTC | `> $72,000` | Global liquidity risk-on confirmed |

Verdict: `FULL RISK-ON` (4/4) · `LEANING RISK-ON` (3/4) · `MIXED` (2/4) · `RISK-OFF` (≤1/4)

**Data cards** — detailed breakdown:

- **Equities** — S&P 500, Nasdaq, IHSG/JCI, VIX, HY Spread
- **FX & Rates** — DXY, USD/IDR, UST 2Y, UST 10Y, Fed funds, BI rate, Indonesia 10Y, 2s10s spread
- **Commodities** — Gold, Silver, Nickel, Copper, Aluminium, Tin, CPO
- **Energy** — Brent, WTI, Newcastle Coal, Natural Gas
- **Crypto** — Bitcoin, Ethereum

## Quick start

```bash
git clone git@github.com:ad17-2/macro-tracker.git
cd macro-tracker

pip install -r requirements.txt

# Get a free FRED API key: https://fred.stlouisfed.org/docs/api/api_key.html
echo "FRED_API_KEY=your_key_here" > .env

# Fetch data
python fetch.py

# Serve dashboard
python -m http.server 8765
# Open http://localhost:8765/index.html
```

## Architecture

```
fetch.py          # Fetches + scrapes market data, writes data.json
data.json         # Structured market data output (gitignored)
index.html        # Single-file dashboard, inline CSS + JS
.env              # FRED_API_KEY (gitignored)
requirements.txt  # requests, beautifulsoup4, python-dotenv
```

`fetch.py` runs once, writes `data.json`. `index.html` loads `data.json` via `fetch()` and renders. Zero runtime dependencies on the browser side.

## Data sources

| Source | Auth | Coverage |
|--------|------|----------|
| [Yahoo Finance](https://finance.yahoo.com) | Crumb-based session (no key) | Equities, FX, precious metals, some base metals, energy |
| [FRED API](https://fred.stlouisfed.org/docs/api/fred/) | Free API key | US rates (2Y, 10Y, Fed funds), HY spread |
| [CoinGecko](https://www.coingecko.com/en/api) | None | BTC, ETH |
| [tradingeconomics.com](https://tradingeconomics.com) | Scrape | LME nickel/tin, Newcastle coal, CPO, Indonesia 10Y |
| [bi.go.id](https://www.bi.go.id) | Scrape | BI rate |

If any source fails, affected data points show as `N/A`. Script never crashes on partial failure.

## Signal logic

Every run, the script computes 4 signals from the latest values:

```python
signals = {
  "vix":   value < 20       → clear else caution,
  "dxy":   value < 98       → clear else caution,
  "ust2y": value < 3.50     → clear else caution,
  "btc":   value > 72000    → clear else caution,
}
```

Verdict is the count of clear signals mapped to a label (see table above).

## Customizing

**Change signal thresholds** — edit `compute_signals()` in `fetch.py`.

**Add/remove tickers** — edit the `tickers` dict in `fetch_yahoo_finance()` and add an entry to `build_output()`.

**Change layout/colors** — inline CSS in `index.html`, no framework, plain variables.

## Automating daily refresh

**Local cron** — add to `crontab -e` (runs every weekday at 6pm local):

```cron
0 18 * * 1-5 cd /path/to/macro-tracker && /usr/bin/python fetch.py >> /tmp/macro-tracker.log 2>&1
```

**Deployed** — run `server.py` instead of `fetch.py`. It fetches on startup, re-fetches every `FETCH_INTERVAL_HOURS` (default 12), and serves the dashboard on `$PORT`.

## Deploy to Railway

```bash
railway login
railway init --name macro-tracker
railway variables --set "FRED_API_KEY=your_key_here"
railway up
railway domain
```

Railway auto-detects Python via Nixpacks, installs `requirements.txt`, and runs `python server.py` per `Procfile`. Dashboard refreshes every 12 hours automatically — tune via `FETCH_INTERVAL_HOURS` variable.

## Mobile

Dashboard is responsive — signal cards stack 2x2, data cards single column on narrow screens.

![Mobile](docs/screenshots/dashboard-mobile.png)

## License

MIT.
