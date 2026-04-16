from datetime import datetime, timezone

from analysis import compute_signals, generate_attention
from history import previous_day_snapshot


NAMES = {
    "sp500": "S&P 500", "nasdaq": "Nasdaq", "ihsg": "IHSG/JCI",
    "vix": "VIX", "hy_spread": "HY Spread",
    "dxy": "DXY", "usdidr": "USD/IDR",
    "ust2y": "UST 2Y Yield", "ust10y": "UST 10Y Yield",
    "fed_funds": "Fed Funds Rate", "bi_rate": "BI Rate",
    "indo_10y": "Indonesia 10Y", "spread_2s10s": "2s10s Spread",
    "gold": "Gold (XAU)", "silver": "Silver (XAG)",
    "nickel": "Nickel", "nickel_lme": "Nickel", "copper": "Copper",
    "aluminium": "Aluminium", "tin": "Tin", "cpo": "CPO",
    "brent": "Brent Crude", "wti": "WTI Crude",
    "coal": "Newcastle Coal", "natgas": "Natural Gas",
    "btc": "Bitcoin", "eth": "Ethereum",
}


def build_output(yahoo, fred, crypto, scraped, history=None):
    all_data = {}
    all_data.update(yahoo)
    all_data.update(fred)
    all_data.update(crypto)
    all_data.update(scraped)

    signals, verdict = compute_signals(all_data, history=history)

    prev_snapshot = previous_day_snapshot(history) if history else None
    prev_signals = (prev_snapshot or {}).get("_signals", {})
    for key, signal in signals.items():
        prev = prev_signals.get(key)
        signal["previous_status"] = prev
        signal["flipped"] = prev is not None and prev != signal["status"]

    attention = generate_attention(all_data, fred, scraped, signals, verdict, prev_snapshot)

    spread_2s10s = None
    ust10y = (fred.get("ust10y") or {}).get("value")
    ust2y = (fred.get("ust2y") or {}).get("value")
    if ust10y is not None and ust2y is not None:
        spread_2s10s = round(ust10y - ust2y, 4)

    def entry(key, source=None):
        src = source or all_data
        d = src.get(key, {})
        return {"value": d.get("value"), "change": d.get("change"), "name": NAMES.get(key, key)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "verdict": verdict,
        "attention": attention,
        "equities": {
            "sp500": entry("sp500"),
            "nasdaq": entry("nasdaq"),
            "ihsg": entry("ihsg"),
            "vix": entry("vix"),
            "hy_spread": entry("hy_spread", fred),
        },
        "fx_rates": {
            "dxy": entry("dxy"),
            "usdidr": entry("usdidr"),
            "ust2y": entry("ust2y", fred),
            "ust10y": entry("ust10y", fred),
            "fed_funds": entry("fed_funds", fred),
            "bi_rate": entry("bi_rate", scraped),
            "indo_10y": entry("indo_10y", scraped),
            "spread_2s10s": {
                "value": spread_2s10s,
                "change": None,
                "name": "2s10s Spread",
            },
        },
        "commodities": {
            "gold": entry("gold"),
            "silver": entry("silver"),
            "nickel": entry("nickel_lme", scraped),
            "copper": entry("copper"),
            "aluminium": entry("aluminium"),
            "tin": entry("tin", scraped),
            "cpo": entry("cpo", scraped),
        },
        "energy": {
            "brent": entry("brent"),
            "wti": entry("wti"),
            "coal": entry("coal", scraped),
            "natgas": entry("natgas"),
        },
        "crypto": {
            "btc": entry("btc", crypto),
            "eth": entry("eth", crypto),
        },
    }
