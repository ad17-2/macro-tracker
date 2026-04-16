import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

from common import HISTORY_DAYS
from history import (
    bootstrap_history_from_yahoo,
    flatten_snapshot,
    load_history,
    save_history,
)
from output import build_output
from scraping import scrape_tradingeconomics
from sources import (
    fetch_coingecko,
    fetch_fred,
    fetch_yahoo_finance,
    get_yahoo_session,
)


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    history_path = os.path.join(base_dir, "history.json")
    data_path = os.path.join(base_dir, "data.json")

    history = load_history(history_path)

    print("Fetching macro data...")

    print("  Yahoo Finance...", end=" ", flush=True)
    try:
        session, crumb = get_yahoo_session()
    except Exception as e:
        print(f"session failed: {e}")
        session, crumb = None, None
    yahoo = fetch_yahoo_finance(session, crumb) if session and crumb else fetch_yahoo_finance()
    print("done")

    if session and crumb:
        bootstrap_history_from_yahoo(session, crumb, history, days=HISTORY_DAYS)

    print("  FRED...", end=" ", flush=True)
    fred = fetch_fred()
    print("done")

    print("  CoinGecko...", end=" ", flush=True)
    crypto = fetch_coingecko()
    print("done")

    print("  tradingeconomics + bi.go.id (scraping)...", end=" ", flush=True)
    scraped = scrape_tradingeconomics()
    print("done")

    output = build_output(yahoo, fred, crypto, scraped, history=history)

    with open(data_path, "w") as f:
        json.dump(output, f, indent=2)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    history.setdefault(today, {}).update(flatten_snapshot(output))
    save_history(history_path, history)

    print(f"\nData written to {data_path}")
    print(f"History entries: {len(history)} (cap {HISTORY_DAYS} days)")
    print(f"Timestamp: {output['timestamp']}")
    print(f"Verdict: {output['verdict']['label']} ({output['verdict']['score']}/{output['verdict']['total']})")
    dxy_mode = (output["signals"].get("dxy") or {}).get("mode")
    print(f"DXY mode: {dxy_mode}")
    if output.get("attention"):
        print("Attention:")
        for b in output["attention"]:
            print(f"  - {b}")

    null_count = 0
    total_count = 0
    for section in ("equities", "fx_rates", "commodities", "energy", "crypto"):
        for key, val in output[section].items():
            total_count += 1
            if val["value"] is None:
                null_count += 1
                print(f"  [N/A] {val['name']}")

    print(f"\nCoverage: {total_count - null_count}/{total_count} data points")


if __name__ == "__main__":
    main()
