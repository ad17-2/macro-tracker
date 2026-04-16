import requests
from bs4 import BeautifulSoup

from common import HEADERS, TIMEOUT


def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[WARN] Fetch failed for {url}: {e}")
        return None


def parse_te_table(soup, name_to_key):
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


def scrape_indo_10y(soup):
    if soup is None:
        return None
    table = soup.find("table")
    if not table:
        return None
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue
        if cells[0].get_text(strip=True) == "Indonesia 10Y":
            result = {"value": None, "change": None}
            try:
                result["value"] = float(cells[1].get_text(strip=True).replace(",", ""))
            except ValueError:
                pass
            try:
                result["change"] = float(cells[3].get_text(strip=True).replace("%", ""))
            except ValueError:
                pass
            return result
    return None


def scrape_bi_rate(soup):
    if soup is None:
        return None
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                text = cells[1].get_text(strip=True).replace("%", "")
                try:
                    return float(text)
                except ValueError:
                    continue
    return None


def scrape_tradingeconomics():
    results = {
        "bi_rate": {"value": None, "change": None},
        "indo_10y": {"value": None, "change": None},
        "coal": {"value": None, "change": None},
        "tin": {"value": None, "change": None},
        "nickel_lme": {"value": None, "change": None},
        "cpo": {"value": None, "change": None},
    }

    metals = parse_te_table(
        fetch_page("https://tradingeconomics.com/commodity/coal"),
        {"Coal": "coal", "Tin": "tin", "Nickel": "nickel_lme"},
    )
    results.update(metals)

    palm = parse_te_table(
        fetch_page("https://tradingeconomics.com/commodity/palm-oil"),
        {"Palm Oil": "cpo"},
    )
    results.update(palm)

    indo = scrape_indo_10y(fetch_page("https://tradingeconomics.com/indonesia/government-bond-yield"))
    if indo:
        results["indo_10y"] = indo

    bi_val = scrape_bi_rate(fetch_page("https://www.bi.go.id/en/statistik/indikator/bi-rate.aspx"))
    if bi_val is not None:
        results["bi_rate"]["value"] = bi_val

    return results
