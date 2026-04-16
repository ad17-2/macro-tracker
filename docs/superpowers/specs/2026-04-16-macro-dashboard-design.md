# Macro Situation Tracker — Design Spec

## Overview

Single-page macro dashboard that displays daily market data with a risk-on/off signal scorecard. Data fetched by a Python script, rendered by a static HTML file.

## Architecture

```
macro-tracker/
  fetch.py          # Python script — scrapes/fetches data, writes data.json
  data.json         # Structured market data output
  index.html        # Single-file dashboard (CSS + JS inline)
  .env              # FRED_API_KEY (gitignored)
  .gitignore
  requirements.txt  # requests, beautifulsoup4, python-dotenv
```

## Data Sources

| Category | Data Points | Source | Method |
|----------|-------------|--------|--------|
| Equities | S&P 500, Nasdaq, IHSG/JCI, VIX | Yahoo Finance | REST (no key) |
| FX | DXY, USD/IDR | Yahoo Finance | REST (no key) |
| US Rates | UST 2Y, UST 10Y, Fed funds, HY Spread | FRED API | REST (free key) |
| ID Rates | BI rate, Indonesia 10Y yield | investing.com | Scrape |
| Precious Metals | Gold, Silver | Yahoo Finance | REST |
| Base Metals | Nickel, Copper, Aluminium, Tin | Yahoo Finance futures | REST |
| Energy | Brent, WTI, Nat Gas | Yahoo Finance | REST |
| Energy | Newcastle Coal | investing.com | Scrape |
| Agri | CPO | investing.com | Scrape |
| Crypto | BTC, ETH | CoinGecko | REST (free key) |

## data.json Schema

```json
{
  "timestamp": "2026-04-16T08:00:00Z",
  "signals": {
    "vix": { "value": 18.33, "threshold": 20, "direction": "below", "status": "clear" },
    "dxy": { "value": 97.94, "threshold": 98, "direction": "below", "status": "clear" },
    "ust2y": { "value": 3.82, "threshold": 3.50, "direction": "below", "status": "caution" },
    "btc": { "value": 84500, "threshold": 72000, "direction": "above", "status": "clear" }
  },
  "verdict": { "score": 3, "total": 4, "label": "LEANING RISK-ON" },
  "equities": {
    "sp500": { "value": 5432.10, "change": 1.2, "name": "S&P 500" },
    "nasdaq": { "value": 16800.50, "change": 0.8, "name": "Nasdaq" },
    "ihsg": { "value": 7200.30, "change": -0.3, "name": "IHSG/JCI" },
    "vix": { "value": 18.33, "change": -4.1, "name": "VIX" },
    "hy_spread": { "value": 3.45, "change": null, "name": "HY Spread" }
  },
  "fx_rates": {
    "dxy": { "value": 97.94, "change": -0.5, "name": "DXY" },
    "usdidr": { "value": 16250, "change": 0.1, "name": "USD/IDR" },
    "ust2y": { "value": 3.82, "change": -0.02, "name": "UST 2Y Yield" },
    "ust10y": { "value": 4.28, "change": -0.05, "name": "UST 10Y Yield" },
    "fed_funds": { "value": 5.33, "change": null, "name": "Fed Funds Rate" },
    "bi_rate": { "value": 6.00, "change": null, "name": "BI Rate" },
    "indo_10y": { "value": 6.85, "change": null, "name": "Indonesia 10Y" },
    "spread_2s10s": { "value": 0.46, "change": null, "name": "2s10s Spread" }
  },
  "commodities": {
    "gold": { "value": 2350.40, "change": 0.3, "name": "Gold (XAU)" },
    "silver": { "value": 28.50, "change": 0.5, "name": "Silver (XAG)" },
    "nickel": { "value": 18500, "change": -1.2, "name": "Nickel" },
    "copper": { "value": 4.52, "change": 0.8, "name": "Copper" },
    "aluminium": { "value": 2450, "change": -0.3, "name": "Aluminium" },
    "tin": { "value": 28000, "change": 0.2, "name": "Tin" },
    "cpo": { "value": 3800, "change": null, "name": "CPO" }
  },
  "energy": {
    "brent": { "value": 82.50, "change": -0.8, "name": "Brent Crude" },
    "wti": { "value": 78.30, "change": -0.9, "name": "WTI Crude" },
    "coal": { "value": 135.00, "change": null, "name": "Newcastle Coal" },
    "natgas": { "value": 2.15, "change": 1.5, "name": "Natural Gas" }
  },
  "crypto": {
    "btc": { "value": 84500, "change": 2.1, "name": "Bitcoin" },
    "eth": { "value": 3200, "change": 1.8, "name": "Ethereum" }
  }
}
```

## Dashboard Layout (index.html)

### 1. Header
- Title: "MACRO TRACKER"
- Subtitle: last updated timestamp from data.json

### 2. Signal Scorecard (hero)
- Large verdict badge: color-coded (green/yellow/orange/red)
  - 4/4 clear = green "FULL RISK-ON"
  - 3/4 = yellow "LEANING RISK-ON"
  - 2/4 = orange "MIXED"
  - 1/4 or 0/4 = red "RISK-OFF"
- Score text: "3/4 signals clear"
- Four signal cards in a row:
  - VIX | DXY | UST 2Y | BTC
  - Each shows: name, value, threshold, clear/caution badge
  - Green tint if clear, red tint if caution

### 3. Data Cards Grid
2 columns on desktop (>768px), 1 column on mobile. 5 cards:

- **Equities**: S&P 500, Nasdaq, IHSG/JCI, VIX, HY Spread
- **FX & Rates**: DXY, USD/IDR, UST 2Y, UST 10Y, Fed funds, BI rate, Indo 10Y, 2s10s spread
- **Commodities**: Gold, Silver, Nickel, Copper, Aluminium, Tin, CPO
- **Energy**: Brent, WTI, Newcastle Coal, Nat Gas
- **Crypto**: BTC, ETH

Each card row: `Name    Value    Change%`
- Positive change: green text + up arrow
- Negative change: red text + down arrow
- Null change: gray "—"
- Null value: gray "N/A"

### 4. Style
- Light background (#f5f5f5), white cards with subtle shadow
- System sans-serif fonts
- No external dependencies (no CDN, no fonts, no icons — just unicode arrows)
- Responsive via CSS grid
- All CSS + JS inline in single HTML file

## fetch.py Flow

1. Load .env (FRED_API_KEY)
2. Fetch Yahoo Finance (batch URL with all tickers)
3. Fetch FRED (UST 2Y, UST 10Y, Fed funds, HY Spread)
4. Fetch CoinGecko (BTC, ETH)
5. Scrape investing.com (BI rate, Indo 10Y, Newcastle coal, CPO)
6. Compute derived: 2s10s spread, signal statuses, verdict
7. Write data.json
8. Print summary

### Error handling
- Each source wrapped in try/except
- Failed source → values set to null, warning printed
- Script never crashes on partial failure

### Dependencies
- requests
- beautifulsoup4
- python-dotenv

## Signal Logic

| Signal | Threshold | Clear when | Status |
|--------|-----------|------------|--------|
| VIX | 20 | value < 20 | below threshold = clear |
| DXY | 98 | value < 98 | below threshold = clear |
| UST 2Y | 3.50% | value < 3.50 | below threshold = clear |
| BTC | $72,000 | value > 72,000 | above threshold = clear |

Verdict mapping:
- 4/4 clear → "FULL RISK-ON"
- 3/4 clear → "LEANING RISK-ON"
- 2/4 clear → "MIXED"
- 1/4 or 0/4 clear → "RISK-OFF"

## Usage

```bash
pip install requests beautifulsoup4 python-dotenv
echo "FRED_API_KEY=your_key" > .env
python fetch.py
open index.html
```
