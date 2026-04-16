import json
import os
from datetime import datetime, timezone

from common import HISTORY_DAYS, YAHOO_TICKERS


def load_history(path):
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Failed to load history: {e}")
        return {}


def save_history(path, history):
    dates = sorted(history.keys())
    if len(dates) > HISTORY_DAYS:
        for old in dates[:-HISTORY_DAYS]:
            del history[old]
    with open(path, "w") as f:
        json.dump(history, f, indent=2)


def flatten_snapshot(output):
    flat = {}
    for section in ("equities", "fx_rates", "commodities", "energy", "crypto"):
        for key, item in output.get(section, {}).items():
            if item.get("value") is not None:
                flat[key] = item["value"]
    flat["_signals"] = {k: s["status"] for k, s in output.get("signals", {}).items()}
    flat["_verdict_score"] = output.get("verdict", {}).get("score")
    return flat


def previous_day_snapshot(history):
    dates = sorted(history.keys())
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for d in reversed(dates):
        if d < today:
            return history[d]
    return None


def pct_change_over_n_days(history, key, n_days):
    """Return percentage change between most-recent and n_days ago. None if insufficient data."""
    dates = sorted(history.keys())
    if len(dates) < 2:
        return None
    series = [(d, history[d].get(key)) for d in dates if isinstance(history[d].get(key), (int, float))]
    if len(series) < 2:
        return None
    latest_date, latest_val = series[-1]
    earliest = series[0]
    for date_str, _ in series:
        days_ago = (datetime.strptime(latest_date, "%Y-%m-%d") - datetime.strptime(date_str, "%Y-%m-%d")).days
        if days_ago <= n_days:
            earliest = (date_str, history[date_str].get(key))
            break
    for date_str, val in series:
        days_ago = (datetime.strptime(latest_date, "%Y-%m-%d") - datetime.strptime(date_str, "%Y-%m-%d")).days
        if days_ago >= n_days:
            earliest = (date_str, val)
    earliest_val = earliest[1]
    if earliest_val is None or earliest_val == 0:
        return None
    return round((latest_val - earliest_val) / earliest_val * 100, 3)


def bootstrap_history_from_yahoo(session, crumb, history, days=30):
    """Populate history with past N days of Yahoo Finance data if history is sparse."""
    from sources import fetch_yahoo_chart

    if len(history) >= 5:
        return 0

    print(f"  Bootstrapping history from Yahoo ({days}d)...", end=" ", flush=True)
    inserted_dates = set()

    for key, symbol in YAHOO_TICKERS.items():
        points = fetch_yahoo_chart(session, crumb, symbol, range_str=f"{days}d", interval="1d")
        for date_str, close in points:
            if date_str not in history:
                history[date_str] = {}
            if key not in history[date_str]:
                history[date_str][key] = close
                inserted_dates.add(date_str)

    print(f"done ({len(inserted_dates)} days seeded)")
    return len(inserted_dates)
