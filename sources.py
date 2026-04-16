import os
from datetime import datetime, timezone

import requests

from common import HEADERS, TIMEOUT, YAHOO_TICKERS

FRED_API_KEY = os.getenv("FRED_API_KEY")


def get_yahoo_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    session.get("https://finance.yahoo.com/quote/%5EGSPC/", timeout=TIMEOUT)
    crumb = session.get("https://query2.finance.yahoo.com/v1/test/getcrumb", timeout=TIMEOUT).text
    return session, crumb


def fetch_yahoo_finance(session=None, crumb=None):
    if session is None or crumb is None:
        try:
            session, crumb = get_yahoo_session()
        except Exception as e:
            print(f"[WARN] Yahoo Finance session failed: {e}")
            return {k: {"value": None, "change": None} for k in YAHOO_TICKERS}

    try:
        symbols = ",".join(YAHOO_TICKERS.values())
        resp = session.get(
            "https://query2.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbols, "crumb": crumb},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[WARN] Yahoo Finance quote failed: {e}")
        return {k: {"value": None, "change": None} for k in YAHOO_TICKERS}

    quotes = {q["symbol"]: q for q in data.get("quoteResponse", {}).get("result", [])}
    results = {}
    for key, symbol in YAHOO_TICKERS.items():
        quote = quotes.get(symbol, {})
        price = quote.get("regularMarketPrice")
        change_pct = quote.get("regularMarketChangePercent")
        if price is not None:
            price = round(price, 4)
        if change_pct is not None:
            change_pct = round(change_pct, 2)
        results[key] = {"value": price, "change": change_pct}
    return results


def fetch_yahoo_chart(session, crumb, symbol, range_str="1mo", interval="1d"):
    """Return list of (date_str, close) for a single symbol, sorted ascending."""
    try:
        resp = session.get(
            f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range": range_str, "interval": interval, "crumb": crumb},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            return []
        r = result[0]
        timestamps = r.get("timestamp") or []
        closes = (r.get("indicators", {}).get("quote", [{}])[0] or {}).get("close") or []
        out = []
        for ts, close in zip(timestamps, closes):
            if close is None:
                continue
            date_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
            out.append((date_str, round(float(close), 4)))
        return out
    except Exception as e:
        print(f"[WARN] Yahoo chart {symbol} failed: {e}")
        return []


def fetch_fred():
    if not FRED_API_KEY:
        print("[WARN] FRED_API_KEY not set, skipping FRED data")
        return {
            "ust2y": {"value": None, "change": None},
            "ust10y": {"value": None, "change": None},
            "fed_funds": {"value": None, "change": None},
            "hy_spread": {"value": None, "change": None},
        }

    series = {
        "ust2y": "DGS2",
        "ust10y": "DGS10",
        "fed_funds": "DFF",
        "hy_spread": "BAMLH0A0HYM2",
    }

    results = {}
    for key, series_id in series.items():
        try:
            resp = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": FRED_API_KEY,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 5,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            observations = resp.json().get("observations", [])
            valid = [o for o in observations if o.get("value") not in (".", None, "")]
            if valid:
                current = float(valid[0]["value"])
                prev = float(valid[1]["value"]) if len(valid) >= 2 else None
                change = round(current - prev, 4) if prev is not None else None
                results[key] = {"value": round(current, 4), "change": change}
            else:
                results[key] = {"value": None, "change": None}
        except Exception as e:
            print(f"[WARN] FRED {series_id} failed: {e}")
            results[key] = {"value": None, "change": None}

    return results


def fetch_coingecko():
    url = (
        "https://api.coingecko.com/api/v3/simple/price"
        "?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        return {
            "btc": {
                "value": data.get("bitcoin", {}).get("usd"),
                "change": round(data.get("bitcoin", {}).get("usd_24h_change", 0), 2),
            },
            "eth": {
                "value": data.get("ethereum", {}).get("usd"),
                "change": round(data.get("ethereum", {}).get("usd_24h_change", 0), 2),
            },
        }
    except Exception as e:
        print(f"[WARN] CoinGecko failed: {e}")
        return {
            "btc": {"value": None, "change": None},
            "eth": {"value": None, "change": None},
        }
