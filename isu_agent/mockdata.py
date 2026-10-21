"""Generate a mock SAP IS-U dataset with deliberately planted billing anomalies.

Table and field names are modelled on SAP IS-U (BUT000, FKKVKP, EVER, EANL,
EGERH, EABL, ERCH, DBERCHZ) but simplified. All data is synthetic.

Code values used in this mock (documented in README):
  EABL.ISTABLART  01 = read by utility, 02 = read by customer, 03 = automatic estimation
  EABL.ABLESGR    01 = periodic read, 21 = device installation, 22 = device removal
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

from . import config

SCHEMA = """
CREATE TABLE but000 (partner TEXT PRIMARY KEY, name TEXT, city TEXT);
CREATE TABLE fkkvkp (vkont TEXT PRIMARY KEY, partner TEXT);
CREATE TABLE eanl   (anlage TEXT PRIMARY KEY, vstelle TEXT, tariftyp TEXT, sparte TEXT);
CREATE TABLE ever   (vertrag TEXT PRIMARY KEY, vkont TEXT, anlage TEXT, einzdat TEXT, auszdat TEXT);
CREATE TABLE egerh  (equnr TEXT, anlage TEXT, sernr TEXT, ab TEXT, bis TEXT, faktor REAL, PRIMARY KEY (equnr, anlage));
CREATE TABLE eabl   (ablbelnr TEXT PRIMARY KEY, equnr TEXT, adat TEXT, zwstand REAL, istablart TEXT, ablesgr TEXT);
CREATE TABLE rates  (tariftyp TEXT, ab TEXT, bis TEXT, energy_price REAL, PRIMARY KEY (tariftyp, ab));
CREATE TABLE erch   (belnr TEXT PRIMARY KEY, vertrag TEXT, abrdats TEXT, abrdate TEXT, kwh REAL,
                     net_amount REAL, vat_amount REAL, gross_amount REAL, waers TEXT,
                     stokz TEXT, reversed_by TEXT, created_on TEXT);
CREATE TABLE dberchz(belnr TEXT, belzeile INTEGER, line_type TEXT, ab TEXT, bis TEXT,
                     quantity REAL, unit TEXT, price REAL, amount REAL, PRIMARY KEY (belnr, belzeile));
CREATE TABLE code_texts (field TEXT, code TEXT, text TEXT, PRIMARY KEY (field, code));
CREATE TABLE clarif_case (case_id INTEGER PRIMARY KEY AUTOINCREMENT, vkont TEXT, belnr TEXT,
                          category TEXT, summary TEXT, status TEXT, created_on TEXT);
"""

CODE_TEXTS = [
    ("ISTABLART", "01", "Meter read by utility"),
    ("ISTABLART", "02", "Meter read by customer"),
    ("ISTABLART", "03", "Automatic estimation"),
    ("ABLESGR", "01", "Periodic meter reading"),
    ("ABLESGR", "21", "Meter reading at device installation"),
    ("ABLESGR", "22", "Meter reading at device removal"),
]

SCENARIOS = {
    "NORMAL": 12,
    "ESTIMATE_CATCHUP": 4,
    "RATE_CHANGE": 4,
    "METER_FACTOR": 4,
    "REVERSAL_REBILL": 4,
    "LONG_PERIOD": 4,
    "SEASONAL_HEATING": 4,
    "USAGE_SPIKE": 4,
}

QUESTIONS = {
    "NORMAL": "Customer says the latest bill feels high. Is anything wrong?",
    "ESTIMATE_CATCHUP": "Why is this customer's latest bill so much higher than the last few months?",
    "RATE_CHANGE": "Consumption looks the same but the bill went up. Why?",
    "METER_FACTOR": "The latest bill is enormous. What happened?",
    "REVERSAL_REBILL": "Customer says they were billed twice this month. Explain.",
    "LONG_PERIOD": "Why is the latest bill almost double the usual amount?",
    "SEASONAL_HEATING": "Why was the January bill so high?",
    "USAGE_SPIKE": "Why did consumption jump on the latest bill?",
}

FIRST_NAMES = ["Anna", "Lukas", "Mia", "Jonas", "Lea", "Felix", "Sophie", "Paul", "Emma", "Leon",
               "Hannah", "Finn", "Lina", "Noah", "Clara", "Elias", "Marie", "Ben", "Laura", "Tim"]
LAST_NAMES = ["Muller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker",
              "Hoffmann", "Koch", "Richter", "Klein", "Wolf", "Neumann", "Braun", "Zimmermann"]
CITIES = ["Berlin", "Hamburg", "Munich", "Cologne", "Frankfurt", "Stuttgart", "Dusseldorf", "Leipzig"]

TARIFFS = {
    # tariftyp: list of (valid_from, valid_to, energy price EUR/kWh)
    "RES_STD": [("2024-01-01", "9999-12-31", 0.32)],
    "RES_FLEX": [("2024-01-01", "2026-08-31", 0.30), ("2026-09-01", "9999-12-31", 0.42)],
    "RES_HEAT": [("2024-01-01", "9999-12-31", 0.27)],
}


def month_end_dates(start: date, count: int) -> list[date]:
    """Return `count` consecutive month-end dates starting with `start` (a month end)."""
    out, d = [], start
    for _ in range(count):
        out.append(d)
        nxt = (d + timedelta(days=1)).replace(day=28) + timedelta(days=4)
        d = nxt - timedelta(days=nxt.day)  # last day of following month
    return out


READ_DATES = month_end_dates(date(2024, 9, 30), 25)  # 2024-09-30 .. 2026-09-30 -> 24 bills
FOCUS_LATEST = (READ_DATES[-2], READ_DATES[-1])
FOCUS_JANUARY = (date(2025, 12, 31), date(2026, 1, 31))


@dataclass
class Counters:
    values: dict = field(default_factory=lambda: {"partner": 1000000000, "vkont": 100000000000,
                                                  "anlage": 4000000000, "vertrag": 3000000000,
                                                  "equnr": 10000000, "abl": 500000000000,
                                                  "belnr": 700000000000})

    def next(self, key: str) -> str:
        self.values[key] += 1
        return str(self.values[key])


def daily_kwh(base: float, d: date, scenario: str, rng: random.Random) -> float:
    """Return true daily consumption for one day."""
    phase = 2 * math.pi * (d.month - 1) / 12
    if scenario == "SEASONAL_HEATING":
        factor = 1 + 1.2 * max(0.0, math.cos(phase))   # strong winter peak (electric heating)
    else:
        factor = 1 + 0.12 * math.cos(phase)             # mild seasonality
    return base * factor * rng.uniform(0.97, 1.03)


def tariff_price(tariftyp: str, d: date) -> float:
    for ab, bis, price in TARIFFS[tariftyp]:
        if date.fromisoformat(ab) <= d <= date.fromisoformat(bis):
            return price
    raise ValueError(f"No price for {tariftyp} on {d}")


def generate(db_path=config.DB_PATH, seed: int = 42) -> dict:
    rng = random.Random(seed)
    cnt = Counters()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO code_texts VALUES (?,?,?)", CODE_TEXTS)
    for t, rows in TARIFFS.items():
        con.executemany("INSERT INTO rates VALUES (?,?,?,?)", [(t, a, b, p) for a, b, p in rows])

    ground_truth = []
    for scenario, n in SCENARIOS.items():
        for _ in range(n):
            gt = _build_account(con, cnt, rng, scenario)
            ground_truth.append(gt)
    con.commit()
    con.close()

    config.GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GROUND_TRUTH_PATH.write_text(json.dumps(ground_truth, indent=2))
    return {"accounts": len(ground_truth), "db": str(db_path)}


def _build_account(con, cnt: Counters, rng: random.Random, scenario: str) -> dict:
    partner, vkont = cnt.next("partner"), cnt.next("vkont")
    anlage, vertrag = cnt.next("anlage"), cnt.next("vertrag")
    name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
    tariftyp = {"RATE_CHANGE": "RES_FLEX", "SEASONAL_HEATING": "RES_HEAT"}.get(scenario, "RES_STD")
    base = rng.uniform(6.0, 13.0)

    con.execute("INSERT INTO but000 VALUES (?,?,?)", (partner, name, rng.choice(CITIES)))
    con.execute("INSERT INTO fkkvkp VALUES (?,?)", (vkont, partner))
    con.execute("INSERT INTO eanl VALUES (?,?,?,?)", (anlage, f"PREM-{anlage[-6:]}", tariftyp, "01"))
    con.execute("INSERT INTO ever VALUES (?,?,?,?,?)",
                (vertrag, vkont, anlage, READ_DATES[0].isoformat(), "9999-12-31"))

    # ---- Devices -------------------------------------------------------------
    dev1, sern1 = cnt.next("equnr"), f"MTR-{rng.randint(100000, 999999)}"
    replace_day = date(2026, 9, 10) if scenario == "METER_FACTOR" else None
    con.execute("INSERT INTO egerh VALUES (?,?,?,?,?,?)",
                (dev1, anlage, sern1, READ_DATES[0].isoformat(),
                 (replace_day.isoformat() if replace_day else "9999-12-31"), 1.0))
    dev2 = None
    if replace_day:
        dev2 = cnt.next("equnr")
        # Planted error: multiplication factor maintained as 10 instead of 1
        con.execute("INSERT INTO egerh VALUES (?,?,?,?,?,?)",
                    (dev2, anlage, f"MTR-{rng.randint(100000, 999999)}", replace_day.isoformat(), "9999-12-31", 10.0))

    # ---- True cumulative consumption per day --------------------------------
    true_reading = {READ_DATES[0]: 0.0}
    cum, d = 0.0, READ_DATES[0]
    while d < READ_DATES[-1]:
        d += timedelta(days=1)
        use = daily_kwh(base, d, scenario, rng)
        if scenario == "USAGE_SPIKE" and d > FOCUS_LATEST[0]:
            use *= 1.8   # e.g. new appliance or fault at premise
        cum += use
        true_reading[d] = cum

    start_reading = rng.uniform(10000, 40000)

    # ---- Meter reads (EABL) ---------------------------------------------------
    reads = []  # (date, device, value, istablart, ablesgr)
    est_dates = set(READ_DATES[-4:-1]) if scenario == "ESTIMATE_CATCHUP" else set()
    skip_dates = {READ_DATES[-2]} if scenario == "LONG_PERIOD" else set()
    last_recorded = None
    for i, rd in enumerate(READ_DATES):
        if rd in skip_dates:
            continue
        if replace_day and rd == READ_DATES[-1]:
            # removal read on old device, installation + periodic read on new device
            reads.append((replace_day, dev1, start_reading + true_reading[replace_day], "01", "22"))
            new_start = 50.0
            reads.append((replace_day, dev2, new_start, "01", "21"))
            reads.append((rd, dev2, new_start + (true_reading[rd] - true_reading[replace_day]), "01", "01"))
            continue
        if rd in est_dates:
            # Under-estimation: system assumes only 60% of real usage since last actual read
            prev_val = last_recorded[1]
            prev_date = last_recorded[0]
            est = prev_val + 0.6 * (true_reading[rd] - true_reading[prev_date])
            reads.append((rd, dev1, est, "03", "01"))
            last_recorded = (rd, est)
            continue
        val = start_reading + true_reading[rd]
        reads.append((rd, dev1, val, rng.choice(["01", "01", "01", "02"]), "01"))
        last_recorded = (rd, val)
    for r in reads:
        con.execute("INSERT INTO eabl VALUES (?,?,?,?,?,?)",
                    (cnt.next("abl"), r[1], r[0].isoformat(), round(r[2], 1), r[3], r[4]))

    # ---- Billing (ERCH / DBERCHZ) -------------------------------------------
    periodic = [r for r in reads if r[4] == "01"]
    factors = {dev1: 1.0, **({dev2: 10.0} if dev2 else {})}
    focus_belnr, reversed_belnr = None, None
    for prev, cur in zip(periodic, periodic[1:]):
        p_start, p_end = prev[0], cur[0]
        if replace_day and p_start < replace_day <= p_end:
            kwh = (reads[-3][2] - prev[2]) * factors[dev1] + (cur[2] - reads[-2][2]) * factors[dev2]
        else:
            kwh = (cur[2] - prev[2]) * factors[cur[1]]
        focus = (p_start, p_end) == (FOCUS_JANUARY if scenario == "SEASONAL_HEATING" else
                                     ((READ_DATES[-3], READ_DATES[-1]) if scenario == "LONG_PERIOD" else FOCUS_LATEST))
        if scenario == "REVERSAL_REBILL" and focus:
            # First bill used an implausible read (+40%), was reversed and rebilled correctly
            wrong = _post_bill(con, cnt, vertrag, tariftyp, p_start, p_end, kwh * 1.4, created=p_end + timedelta(days=2))
            reversed_belnr = wrong
            belnr = _post_bill(con, cnt, vertrag, tariftyp, p_start, p_end, kwh, created=p_end + timedelta(days=6))
            con.execute("UPDATE erch SET stokz='X', reversed_by=? WHERE belnr=?", (belnr, wrong))
        else:
            belnr = _post_bill(con, cnt, vertrag, tariftyp, p_start, p_end, kwh, created=p_end + timedelta(days=2))
        if focus:
            focus_belnr = belnr

    return {"vkont": vkont, "partner": partner, "name": name, "scenario": scenario,
            "focus_belnr": focus_belnr, "reversed_belnr": reversed_belnr,
            "question": QUESTIONS[scenario]}


def _post_bill(con, cnt, vertrag, tariftyp, start: date, end: date, kwh: float, created: date) -> str:
    belnr = cnt.next("belnr")
    days = (end - start).days
    lines, net = [], 0.0
    # Split energy line at price changes (prorated by days)
    segments, seg_start = [], start
    d = start
    while d < end:
        d += timedelta(days=1)
        if d == end or tariff_price(tariftyp, d + timedelta(days=1)) != tariff_price(tariftyp, d):
            segments.append((seg_start, d))
            seg_start = d
    for s, e in segments:
        seg_days = (e - s).days
        q = kwh * seg_days / days
        price = tariff_price(tariftyp, e)
        amt = round(q * price, 2)
        lines.append(("ENERGY", s, e, round(q, 1), "KWH", price, amt))
        net += amt
    fixed = round(days * config.FIXED_CHARGE_PER_DAY, 2)
    lines.append(("FIXED", start, end, days, "DAY", config.FIXED_CHARGE_PER_DAY, fixed))
    net = round(net + fixed, 2)
    vat = round(net * config.VAT_RATE, 2)
    lines.append(("VAT", start, end, net, config.CURRENCY, config.VAT_RATE, vat))
    con.execute("INSERT INTO erch VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (belnr, vertrag, start.isoformat(), end.isoformat(), round(kwh, 1), net, vat,
                 round(net + vat, 2), config.CURRENCY, "", "", created.isoformat()))
    for i, (lt, s, e, q, u, p, a) in enumerate(lines, start=1):
        con.execute("INSERT INTO dberchz VALUES (?,?,?,?,?,?,?,?,?)",
                    (belnr, i, lt, s.isoformat(), e.isoformat(), q, u, p, a))
    return belnr


if __name__ == "__main__":
    print(generate())
