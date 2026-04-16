from history import pct_change_over_n_days


DXY_STATIC_THRESHOLD = 98
DXY_LEVEL_CAP = 99
DXY_TREND_WINDOW_DAYS = 30
DXY_TREND_THRESHOLD = -0.5


def _value_of(src, key):
    return (src.get(key) or {}).get("value")


def _change_of(src, key):
    return (src.get(key) or {}).get("change")


def compute_signals(data, history=None):
    vix_val = _value_of(data, "vix")
    dxy_val = _value_of(data, "dxy")
    ust2y_val = _value_of(data, "ust2y")
    fed_funds_val = _value_of(data, "fed_funds")
    hy_spread_val = _value_of(data, "hy_spread")

    rate_cut_spread = None
    if ust2y_val is not None and fed_funds_val is not None:
        rate_cut_spread = round(ust2y_val - fed_funds_val, 4)

    dxy_signal = _build_dxy_signal(dxy_val, history)

    signals = {
        "vix": {
            "value": vix_val,
            "threshold": 20,
            "direction": "below",
            "status": "clear" if vix_val is not None and vix_val < 20 else "caution",
        },
        "dxy": dxy_signal,
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
    labels = {4: "FULL RISK-ON", 3: "LEANING RISK-ON", 2: "MIXED", 1: "RISK-OFF", 0: "RISK-OFF"}

    verdict = {"score": clear_count, "total": 4, "label": labels[clear_count]}
    return signals, verdict


def _build_dxy_signal(value, history):
    if value is None:
        return {"value": None, "threshold": DXY_STATIC_THRESHOLD, "direction": "below", "mode": "static", "status": "caution"}

    change_30d = None
    if history:
        change_30d = pct_change_over_n_days(history, "dxy", DXY_TREND_WINDOW_DAYS)

    if change_30d is not None and _history_span_days(history) >= DXY_TREND_WINDOW_DAYS - 5:
        clear = value < DXY_LEVEL_CAP and change_30d < DXY_TREND_THRESHOLD
        return {
            "value": value,
            "change_30d": change_30d,
            "level_cap": DXY_LEVEL_CAP,
            "trend_threshold": DXY_TREND_THRESHOLD,
            "mode": "trend",
            "direction": "below",
            "status": "clear" if clear else "caution",
        }

    return {
        "value": value,
        "threshold": DXY_STATIC_THRESHOLD,
        "mode": "static",
        "direction": "below",
        "status": "clear" if value < DXY_STATIC_THRESHOLD else "caution",
    }


def _history_span_days(history):
    if not history:
        return 0
    from datetime import datetime
    dates = sorted(history.keys())
    if len(dates) < 2:
        return 0
    first = datetime.strptime(dates[0], "%Y-%m-%d")
    last = datetime.strptime(dates[-1], "%Y-%m-%d")
    return (last - first).days


def generate_attention(data, fred, scraped, signals, verdict, prev_snapshot):
    bullets = []

    vix = _value_of(data, "vix")
    if vix is not None and vix > 25:
        bullets.append(f"VIX at {vix:.1f} — fear elevated, defensive positioning warranted")

    idr_chg = _change_of(data, "usdidr")
    idr_val = _value_of(data, "usdidr")
    if idr_chg is not None and idr_val is not None and abs(idr_chg) > 0.5:
        direction = "weakening" if idr_chg > 0 else "strengthening"
        bullets.append(f"IDR {direction} {abs(idr_chg):.2f}% to {idr_val:,.0f} — watch import costs / BI policy")

    nickel_chg = _change_of(scraped, "nickel_lme")
    if nickel_chg is not None and abs(nickel_chg) > 2:
        direction = "surged" if nickel_chg > 0 else "dropped"
        bullets.append(f"Nickel {direction} {abs(nickel_chg):.2f}% — top Indonesian export, earnings impact")

    coal_chg = _change_of(scraped, "coal")
    if coal_chg is not None and abs(coal_chg) > 2:
        direction = "up" if coal_chg > 0 else "down"
        bullets.append(f"Newcastle coal {direction} {abs(coal_chg):.2f}% — Indonesian coal exporter impact")

    cpo_chg = _change_of(scraped, "cpo")
    if cpo_chg is not None and abs(cpo_chg) > 2:
        direction = "up" if cpo_chg > 0 else "down"
        bullets.append(f"CPO {direction} {abs(cpo_chg):.2f}% — palm oil relevance for Indonesian agri")

    tin_chg = _change_of(scraped, "tin")
    if tin_chg is not None and abs(tin_chg) > 2:
        direction = "up" if tin_chg > 0 else "down"
        bullets.append(f"Tin {direction} {abs(tin_chg):.2f}% — Indonesia top global producer")

    brent_chg = _change_of(data, "brent")
    if brent_chg is not None and abs(brent_chg) > 3:
        direction = "spiked" if brent_chg > 0 else "dropped"
        bullets.append(f"Brent {direction} {abs(brent_chg):.2f}% — energy shock, watch inflation / fuel subsidy pressure")

    hy_val = _value_of(fred, "hy_spread")
    if hy_val is not None and hy_val > 4.5:
        bullets.append(f"HY spread at {hy_val:.2f}% — credit stress building, risk-off regime")

    rc_val = (signals.get("rate_cut_spread") or {}).get("value")
    if rc_val is not None and rc_val < -0.5:
        bullets.append(f"2Y-Fed at {rc_val:+.2f}% — market pricing aggressive cuts, liquidity incoming")

    dxy_sig = signals.get("dxy") or {}
    dxy_change_30d = dxy_sig.get("change_30d")
    if dxy_change_30d is not None and abs(dxy_change_30d) > 1.5:
        direction = "weakening" if dxy_change_30d < 0 else "strengthening"
        bullets.append(f"DXY {direction} {abs(dxy_change_30d):.2f}% over 30d — {'EM tailwind' if dxy_change_30d < 0 else 'EM headwind'}")

    if prev_snapshot:
        prev_score = prev_snapshot.get("_verdict_score")
        today_score = verdict.get("score")
        if prev_score is not None and today_score is not None and prev_score != today_score:
            trend = "improving" if today_score > prev_score else "deteriorating"
            bullets.append(f"Scorecard {trend}: {prev_score}/4 yesterday \u2192 {today_score}/4 today")

    if not bullets:
        if verdict["score"] >= 3:
            bullets.append("All quiet \u2014 risk signals aligned, markets calm")
        elif verdict["score"] <= 1:
            bullets.append("Risk-off regime persists \u2014 watch for flight-to-quality moves")
        else:
            bullets.append("Mixed signals \u2014 no major moves, stay selective")

    return bullets[:5]
