"""Deterministic IS-U bill anomaly checks.

The LLM never calculates on its own: it calls `analyze_bill`, which returns
facts with evidence. This keeps explanations grounded and testable.
"""
from __future__ import annotations

from datetime import date
from statistics import median

from . import config

# Highest priority first: the first finding is reported as the primary cause
PRIORITY = ["METER_FACTOR", "LONG_PERIOD", "ESTIMATE_CATCHUP", "REVERSAL_REBILL",
            "RATE_CHANGE", "SEASONAL_HEATING", "USAGE_SPIKE"]

CAUSE_TEXT = {
    "METER_FACTOR": "Device replacement with an incorrect multiplication factor",
    "LONG_PERIOD": "Billing period longer than usual (a scheduled read was missed)",
    "ESTIMATE_CATCHUP": "Catch-up after a series of under-estimated meter reads",
    "REVERSAL_REBILL": "Original bill reversed and rebilled (two documents, one valid charge)",
    "RATE_CHANGE": "Energy price increase for the customer's rate category",
    "SEASONAL_HEATING": "Seasonal consumption peak, consistent with the same period last year",
    "USAGE_SPIKE": "Genuine consumption increase not explained by billing or device events",
    "NORMAL": "Bill is in line with the customer's history",
}

ACTIONS = {
    "METER_FACTOR": "Correct the register factor on the new device, reverse the bill and rebill. Raise an internal case for device management.",
    "LONG_PERIOD": "Explain the longer period; offer an instalment plan. Check why the scheduled read was missed.",
    "ESTIMATE_CATCHUP": "Explain the catch-up; offer an instalment plan; schedule an actual read or ask for customer self-reads to avoid repeated estimation.",
    "REVERSAL_REBILL": "Reassure the customer: only the rebilled document is payable; the reversed document is cancelled.",
    "RATE_CHANGE": "Explain the price change and its effective date; check eligibility for a cheaper rate category.",
    "SEASONAL_HEATING": "Explain the seasonal pattern; suggest a budget billing plan to spread winter costs.",
    "USAGE_SPIKE": "Ask the customer about new appliances; offer a field check of the meter/installation if not explained.",
    "NORMAL": "No correction needed. Share the consumption comparison with the customer.",
}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _days(doc: dict) -> int:
    return (_d(doc["abrdate"]) - _d(doc["abrdats"])).days


def _daily(doc: dict) -> float:
    return doc["kwh"] / max(_days(doc), 1)


def _energy_price(lines: list[dict]) -> float | None:
    energy = [l for l in lines if l["line_type"] == "ENERGY"]
    return energy[-1]["price"] if energy else None


def analyze_bill(repo, vkont: str, belnr: str | None = None) -> dict:
    """Run all checks for one billing document (latest valid one if not given)."""
    acc = repo.account(vkont)
    if not acc:
        return {"error": f"Contract account {vkont} not found"}
    docs = repo.billing_documents(vkont)
    valid = [d for d in docs if d["stokz"] != "X"]
    if not valid:
        return {"error": "No billing documents"}
    bill = next((d for d in docs if d["belnr"] == belnr), None) if belnr else valid[-1]
    if bill is None:
        return {"error": f"Billing document {belnr} not found for {vkont}"}
    if bill["stokz"] == "X":
        rebill = next((d for d in docs if d["belnr"] == bill["reversed_by"]), None)
        if rebill:
            bill = rebill

    idx = [d["belnr"] for d in valid].index(bill["belnr"])
    history = valid[max(0, idx - 6):idx]
    reads = repo.meter_reads(vkont)
    devices = repo.devices(vkont)
    lines = repo.billing_lines(bill["belnr"])
    findings: list[dict] = []

    p_start, p_end = _d(bill["abrdats"]), _d(bill["abrdate"])
    days = _days(bill)
    daily_now = _daily(bill)

    # Baseline from previous bills whose end read was an actual read
    actual_read_dates = {r["adat"] for r in reads if r["istablart"] in ("01", "02") and r["ablesgr"] == "01"}
    hist_actual = [h for h in history if h["abrdate"] in actual_read_dates and h["abrdats"] in actual_read_dates]
    baseline_src = hist_actual or history
    baseline_daily = median(_daily(h) for h in baseline_src) if baseline_src else daily_now
    baseline_gross = median(h["gross_amount"] / _days(h) for h in history) * days if history else bill["gross_amount"]
    ratio = daily_now / baseline_daily if baseline_daily else 1.0

    # 1. Device replacement with factor change ------------------------------
    for dev in devices:
        ab = _d(dev["ab"])
        if p_start < ab <= p_end:
            prev = [x for x in devices if _d(x["bis"]) == ab and x["equnr"] != dev["equnr"]]
            old_factor = prev[0]["faktor"] if prev else 1.0
            if dev["faktor"] != old_factor:
                days_new = (p_end - ab).days
                expected = baseline_daily * days
                findings.append({
                    "cause": "METER_FACTOR",
                    "evidence": {
                        "device_installed_on": dev["ab"], "new_device_serial": dev["sernr"],
                        "old_factor": old_factor, "new_factor": dev["faktor"],
                        "days_on_new_device": days_new, "billed_kwh": bill["kwh"],
                        "expected_kwh_approx": round(expected, 1),
                    }})

    # 2. Long billing period -------------------------------------------------
    if days > config.LONG_PERIOD_DAYS:
        findings.append({"cause": "LONG_PERIOD", "evidence": {
            "period_days": days, "usual_days": round(median(_days(h) for h in history)) if history else 30,
            "daily_kwh_now": round(daily_now, 2), "daily_kwh_baseline": round(baseline_daily, 2)}})

    # 3. Catch-up after estimated reads --------------------------------------
    periodic = [r for r in reads if r["ablesgr"] == "01"]
    start_read = next((r for r in periodic if r["adat"] == bill["abrdats"]), None)
    end_read = next((r for r in periodic if r["adat"] == bill["abrdate"]), None)
    if start_read and end_read and start_read["istablart"] == "03" and end_read["istablart"] != "03":
        streak = []
        for r in reversed([r for r in periodic if r["adat"] <= bill["abrdats"]]):
            if r["istablart"] != "03":
                break
            streak.append(r["adat"])
        last_actual = next((r for r in reversed(periodic) if r["adat"] < min(streak) and r["istablart"] != "03"), None)
        under_kwh = None
        if last_actual:
            real_days = (_d(end_read["adat"]) - _d(last_actual["adat"])).days
            real_total = end_read["zwstand"] - last_actual["zwstand"]
            billed_before = start_read["zwstand"] - last_actual["zwstand"]
            under_kwh = round(real_total * ((_d(start_read["adat"]) - _d(last_actual["adat"])).days / real_days) - billed_before, 1)
        findings.append({"cause": "ESTIMATE_CATCHUP", "evidence": {
            "estimated_read_dates": sorted(streak), "last_actual_read": last_actual["adat"] if last_actual else None,
            "current_read_type": repo.code_text("ISTABLART", end_read["istablart"]),
            "kwh_under_estimated_in_previous_bills_approx": under_kwh,
            "billed_kwh": bill["kwh"]}})

    # 4. Reversal / rebill in same period ------------------------------------
    rev = [d for d in docs if d["stokz"] == "X" and d["abrdats"] == bill["abrdats"] and d["abrdate"] == bill["abrdate"]]
    if rev:
        findings.append({"cause": "REVERSAL_REBILL", "evidence": {
            "reversed_document": rev[0]["belnr"], "reversed_amount": rev[0]["gross_amount"],
            "valid_document": bill["belnr"], "valid_amount": bill["gross_amount"],
            "reversed_on_or_after": bill["created_on"]}})

    # 5. Price change ---------------------------------------------------------
    price_now = _energy_price(lines)
    if history:
        price_prev = _energy_price(repo.billing_lines(history[-1]["belnr"]))
        if price_now and price_prev and (price_now - price_prev) / price_prev * 100 > config.RATE_INCREASE_PCT:
            rates = repo.rates(acc["tariftyp"])
            eff = next((r["ab"] for r in rates if r["energy_price"] == price_now), None)
            findings.append({"cause": "RATE_CHANGE", "evidence": {
                "rate_category": acc["tariftyp"], "old_price_per_kwh": price_prev, "new_price_per_kwh": price_now,
                "effective_from": eff, "increase_pct": round((price_now - price_prev) / price_prev * 100, 1),
                "extra_net_cost": round(bill["kwh"] * (price_now - price_prev), 2),
                "consumption_ratio_vs_baseline": round(ratio, 2)}})

    # 6/7. Consumption increase: seasonal or genuine ----------------------------
    if ratio > config.SPIKE_RATIO and not any(f["cause"] in ("METER_FACTOR", "ESTIMATE_CATCHUP") for f in findings):
        ly_end = p_end.replace(year=p_end.year - 1)
        last_year = next((d for d in valid if abs((_d(d["abrdate"]) - ly_end).days) <= 3), None)
        lo, hi = config.SEASONAL_TOLERANCE
        if last_year and lo <= daily_now / _daily(last_year) <= hi:
            findings.append({"cause": "SEASONAL_HEATING", "evidence": {
                "daily_kwh_now": round(daily_now, 2), "daily_kwh_same_period_last_year": round(_daily(last_year), 2),
                "daily_kwh_recent_baseline": round(baseline_daily, 2),
                "last_year_document": last_year["belnr"]}})
        else:
            findings.append({"cause": "USAGE_SPIKE", "evidence": {
                "daily_kwh_now": round(daily_now, 2), "daily_kwh_baseline": round(baseline_daily, 2),
                "increase_pct": round((ratio - 1) * 100, 1),
                "same_period_last_year_daily": round(_daily(last_year), 2) if last_year else None,
                "device_changes_in_period": False, "price_change_in_period": False}})

    findings.sort(key=lambda f: PRIORITY.index(f["cause"]))
    primary = findings[0]["cause"] if findings else "NORMAL"
    return {
        "contract_account": vkont,
        "customer": acc["name"],
        "billing_document": bill["belnr"],
        "period": f'{bill["abrdats"]} to {bill["abrdate"]}',
        "period_days": days,
        "billed_kwh": bill["kwh"],
        "gross_amount": bill["gross_amount"],
        "currency": bill["waers"],
        "typical_gross_for_same_length": round(baseline_gross, 2),
        "consumption_ratio_vs_baseline": round(ratio, 2),
        "primary_cause": primary,
        "primary_cause_text": CAUSE_TEXT[primary],
        "findings": findings,
        "recommended_action": ACTIONS[primary],
    }
