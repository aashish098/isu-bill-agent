"""Evaluate the agent against planted ground truth.

Rule-engine mode checks `primary_cause`. LLM mode checks that the agent's
`analyze_bill` call landed on the right cause AND that the written answer
mentions the key evidence (document number / cause keywords)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

from . import config
from .agent import BillAgent
from .repository import get_repository
from .rules import analyze_bill

KEYWORDS = {
    "METER_FACTOR": ["factor"], "LONG_PERIOD": ["days", "period"], "ESTIMATE_CATCHUP": ["estimat"],
    "REVERSAL_REBILL": ["revers"], "RATE_CHANGE": ["price"], "SEASONAL_HEATING": ["last year"],
    "USAGE_SPIKE": ["usage", "consumption"], "NORMAL": ["in line", "no error", "normal", "usual"],
}


def run_eval(use_llm: bool = False) -> dict:
    repo = get_repository()
    truth = json.loads(config.GROUND_TRUTH_PATH.read_text())
    per = defaultdict(Counter)
    confusion = Counter()
    agent = BillAgent(repo, provider="anthropic") if use_llm else None

    for g in truth:
        exp = g["scenario"]
        if use_llm:
            res = agent.ask(g["question"], g["vkont"], g["focus_belnr"])
            got = res.analysis["primary_cause"] if res.analysis else "NONE"
            text_ok = any(k in res.answer.lower() for k in KEYWORDS[exp])
            ok = got == exp and text_ok
        else:
            got = analyze_bill(repo, g["vkont"], g["focus_belnr"])["primary_cause"]
            ok = got == exp
        per[exp]["total"] += 1
        per[exp]["correct"] += int(ok)
        confusion[(exp, got)] += 1

    total = sum(c["total"] for c in per.values())
    correct = sum(c["correct"] for c in per.values())
    print(f"{'Scenario':<18}{'Correct':>8}{'Total':>7}")
    for k, c in per.items():
        print(f"{k:<18}{c['correct']:>8}{c['total']:>7}")
    print(f"\nOverall accuracy: {correct}/{total} = {correct / total:.0%}")
    errors = {f"{e} -> {g}": n for (e, g), n in confusion.items() if e != g}
    if errors:
        print("Misclassifications:", errors)

    # False-positive check: every bill of every NORMAL account should come back NORMAL
    fp = Counter()
    checked = 0
    for g in truth:
        if g["scenario"] != "NORMAL":
            continue
        valid = [d for d in repo.billing_documents(g["vkont"]) if d["stokz"] != "X"][6:]  # need 6 bills of history
        for d in valid:
            checked += 1
            cause = analyze_bill(repo, g["vkont"], d["belnr"])["primary_cause"]
            if cause != "NORMAL":
                fp[cause] += 1
    print(f"False positives on normal bills: {sum(fp.values())}/{checked}" + (f" {dict(fp)}" if fp else ""))
    return {"accuracy": correct / total, "per_scenario": {k: dict(v) for k, v in per.items()},
            "false_positives": sum(fp.values()), "normal_bills_checked": checked}
