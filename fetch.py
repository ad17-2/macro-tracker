import json
import os
import sys
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 15


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


def fetch_yahoo_finance():
    tickers = {
        "sp500": "^GSPC",
        "nasdaq": "^IXIC",
        "ihsg": "^JKSE",
        "vix": "^VIX",
        "dxy": "DX-Y.NYB",
        "usdidr": "USDIDR=X",
        "gold": "GC=F",
        "silver": "SI=F",
        "nickel": "^SPGSIKTR",
        "copper": "HG=F",
        "aluminium": "ALI=F",
        "tin": "TIN=F",
        "brent": "BZ=F",
        "wti": "CL=F",
        "natgas": "NG=F",
    }

    try:
        session, crumb = get_yahoo_session()
        symbols = ",".join(tickers.values())
        resp = session.get(
            "https://query2.finance.yahoo.com/v7/finance/quote",
            params={"symbols": symbols, "crumb": crumb},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[WARN] Yahoo Finance failed: {e}")
        return {k: {"value": None, "change": None} for k in tickers}

    quotes = {q["symbol"]: q for q in data.get("quoteResponse", {}).get("result", [])}
    results = {}

    for key, symbol in tickers.items():
        quote = quotes.get(symbol, {})
        price = quote.get("regularMarketPrice")
        change_pct = quote.get("regularMarketChangePercent")
        if price is not None:
            price = round(price, 4)
        if change_pct is not None:
            change_pct = round(change_pct, 2)
        results[key] = {"value": price, "change": change_pct}

    return results


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
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={FRED_API_KEY}"
                f"&file_type=json&sort_order=desc&limit=5"
            )
            resp = requests.get(url, timeout=TIMEOUT)
            resp.raise_for_status()
            observations = resp.json().get("observations", [])

            valid = [o for o in observations if o.get("value") not in (".", None, "")]
            if len(valid) >= 1:
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
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd&include_24hr_change=true"
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


def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[WARN] Fetch failed for {url}: {e}")
        return None


def parse_te_table(soup, name_to_key):
    """Parse first table on tradingeconomics page. Match rows by name, return dict."""
    out = {}
    if soup is None:
        return out
    table = soup.find("table")
    if not table:
        return out
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        name = cells[0].get_text(strip=True)
        key = name_to_key.get(name)
        if not key:
            continue
        try:
            value = float(cells[1].get_text(strip=True).replace(",", ""))
        except ValueError:
            continue
        change = None
        try:
            change_text = cells[4].get_text(strip=True).replace("%", "").replace(",", "")
            change = float(change_text)
        except (ValueError, IndexError):
            pass
        out[key] = {"value": value, "change": change}
    return out


def scrape_tradingeconomics():
    results = {
        "bi_rate": {"value": None, "change": None},
        "indo_10y": {"value": None, "change": None},
        "coal": {"value": None, "change": None},
        "tin": {"value": None, "change": None},
        "nickel_lme": {"value": None, "change": None},
        "cpo": {"value": None, "change": None},
    }

    coal_soup = fetch_page("https://tradingeconomics.com/commodity/coal")
    metals = parse_te_table(coal_soup, {
        "Coal": "coal",
        "Tin": "tin",
        "Nickel": "nickel_lme",
    })
    for k, v in metals.items():
        results[k] = v

    palm_soup = fetch_page("https://tradingeconomics.com/commodity/palm-oil")
    palm = parse_te_table(palm_soup, {"Palm Oil": "cpo"})
    for k, v in palm.items():
        results[k] = v

    bond_soup = fetch_page("https://tradingeconomics.com/indonesia/government-bond-yield")
    if bond_soup:
        table = bond_soup.find("table")
        if table:
            for row in table.find_all("tr"):
                cells = row.find_all(["td", "th"])
                if len(cells) < 4:
                    continue
                if cells[0].get_text(strip=True) == "Indonesia 10Y":
                    try:
                        results["indo_10y"]["value"] = float(cells[1].get_text(strip=True).replace(",", ""))
                    except ValueError:
                        pass
                    try:
                        change_text = cells[3].get_text(strip=True).replace("%", "")
                        results["indo_10y"]["change"] = float(change_text)
                    except ValueError:
                        pass
                    break

    bi_soup = fetch_page("https://www.bi.go.id/en/statistik/indikator/bi-rate.aspx")
    if bi_soup:
        try:
            for table in bi_soup.find_all("table"):
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        text = cells[1].get_text(strip=True).replace("%", "")
                        try:
                            results["bi_rate"]["value"] = float(text)
                            break
                        except ValueError:
                            continue
                if results["bi_rate"]["value"] is not None:
                    break
        except Exception as e:
            print(f"[WARN] BI rate parse failed: {e}")

    return results


def compute_signals(data):
    vix_val = data.get("vix", {}).get("value")
    dxy_val = data.get("dxy", {}).get("value")
    ust2y_val = data.get("ust2y", {}).get("value")
    fed_funds_val = data.get("fed_funds", {}).get("value")
    hy_spread_val = data.get("hy_spread", {}).get("value")

    rate_cut_spread = None
    if ust2y_val is not None and fed_funds_val is not None:
        rate_cut_spread = round(ust2y_val - fed_funds_val, 4)

    signals = {
        "vix": {
            "value": vix_val,
            "threshold": 20,
            "direction": "below",
            "status": "clear" if vix_val is not None and vix_val < 20 else "caution",
        },
        "dxy": {
            "value": dxy_val,
            "threshold": 98,
            "direction": "below",
            "status": "clear" if dxy_val is not None and dxy_val < 98 else "caution",
        },
        "rate_cut_spread": {
            "value": rate_cut_spread,
            "threshold": -0.25,
            "direction": "below",
            "status": "clear" if rate_cut_spread is not None and rate_cut_spread < -0.25 else "caution",
        },
        "hy_spread": {
            "value": hy_spread_val,
            "threshold": 3.50,
            "direction": "below",
            "status": "clear" if hy_spread_val is not None and hy_spread_val < 3.50 else "caution",
        },
    }

    clear_count = sum(1 for s in signals.values() if s["status"] == "clear")
    labels = {
        4: "FULL RISK-ON",
        3: "LEANING RISK-ON",
        2: "MIXED",
        1: "RISK-OFF",
        0: "RISK-OFF",
    }

    verdict = {
        "score": clear_count,
        "total": 4,
        "label": labels[clear_count],
    }

    return signals, verdict


def build_output(yahoo, fred, crypto, scraped):
    all_data = {}
    all_data.update(yahoo)
    all_data.update(fred)
    all_data.update(crypto)
    all_data.update(scraped)

    signals, verdict = compute_signals(all_data)

    spread_2s10s = None
    ust10y = fred.get("ust10y", {}).get("value")
    ust2y = fred.get("ust2y", {}).get("value")
    if ust10y is not None and ust2y is not None:
        spread_2s10s = round(ust10y - ust2y, 4)

    names = {
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

    def entry(key, source=None):
        src = source or all_data
        d = src.get(key, {})
        return {"value": d.get("value"), "change": d.get("change"), "name": names.get(key, key)}

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "signals": signals,
        "verdict": verdict,
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

    return output


def main():
    print("Fetching macro data...")

    print("  Yahoo Finance...", end=" ", flush=True)
    yahoo = fetch_yahoo_finance()
    print("done")

    print("  FRED...", end=" ", flush=True)
    fred = fetch_fred()
    print("done")

    print("  CoinGecko...", end=" ", flush=True)
    crypto = fetch_coingecko()
    print("done")

    print("  tradingeconomics + bi.go.id (scraping)...", end=" ", flush=True)
    scraped = scrape_tradingeconomics()
    print("done")

    output = build_output(yahoo, fred, crypto, scraped)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nData written to {out_path}")
    print(f"Timestamp: {output['timestamp']}")
    print(f"Verdict: {output['verdict']['label']} ({output['verdict']['score']}/{output['verdict']['total']})")

    null_count = 0
    total_count = 0
    for section in ["equities", "fx_rates", "commodities", "energy", "crypto"]:
        for key, val in output[section].items():
            total_count += 1
            if val["value"] is None:
                null_count += 1
                print(f"  [N/A] {val['name']}")

    print(f"\nCoverage: {total_count - null_count}/{total_count} data points")


if __name__ == "__main__":
    main()
