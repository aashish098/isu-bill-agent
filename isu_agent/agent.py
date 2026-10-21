"""The IS-U Bill Anomaly Explainer agent.

Two modes share the same tools:
  * LLM mode (Anthropic tool use): the model plans which IS-U data to read,
    calls `analyze_bill`, and writes the explanation.
  * Offline mode: deterministic plan + templated explanation. No API key needed,
    useful for demos, tests and as a guardrail fallback.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from . import config
from .tools import TOOL_SPECS, ToolBox

SYSTEM_PROMPT = """You are an SAP IS-U billing specialist assisting a utility customer-service agent.
Your job: explain why a customer's bill looks unusual, using ONLY data returned by your tools.

Rules:
- Read-only. Never claim you changed anything in SAP. You may only PROPOSE a clarification case.
- Always call analyze_bill before concluding. Never invent numbers; quote figures from tool results.
- If the user gives a name, use find_account first. If several accounts match, ask which one.
- Use IS-U terms correctly (contract account, installation, meter reading result, estimation, reversal, rate category).
- Answer in this structure:
  1. **Verdict** - one sentence: is the bill correct, and what is the main cause?
  2. **Evidence** - 3-5 bullets with the key figures (dates, kWh, prices, document numbers).
  3. **What to tell the customer** - 2-3 plain-language sentences, no SAP jargon.
  4. **Recommended action** - what the back office should do. If a correction is needed, call
     propose_clarification_case and say it awaits approval.
"""

ACCOUNT_RE = re.compile(r"\b(1\d{11})\b")
BELNR_RE = re.compile(r"\b(7\d{11})\b")


@dataclass
class AgentResult:
    answer: str
    analysis: dict | None = None
    tool_calls: list[dict] = field(default_factory=list)
    proposed_cases: list[dict] = field(default_factory=list)
    mode: str = "offline"


class BillAgent:
    def __init__(self, repo, provider: str = config.LLM_PROVIDER, model: str = config.LLM_MODEL):
        self.repo = repo
        self.provider = provider
        self.model = model

    def ask(self, question: str, vkont: str | None = None, belnr: str | None = None) -> AgentResult:
        if self.provider == "anthropic":
            return self._ask_llm(question, vkont, belnr)
        return self._ask_offline(question, vkont, belnr)

    # ------------------------------------------------------------------ LLM
    def _ask_llm(self, question, vkont, belnr) -> AgentResult:
        import anthropic

        client = anthropic.Anthropic()
        tb = ToolBox(self.repo)
        context = []
        if vkont:
            context.append(f"Contract account: {vkont}")
        if belnr:
            context.append(f"Billing document: {belnr}")
        user_msg = question + (f"\n\n({'; '.join(context)})" if context else "")
        messages = [{"role": "user", "content": user_msg}]
        calls, analysis = [], None

        for _ in range(config.MAX_AGENT_STEPS):
            resp = client.messages.create(model=self.model, max_tokens=1500, system=SYSTEM_PROMPT,
                                          tools=TOOL_SPECS, messages=messages)
            messages.append({"role": "assistant", "content": resp.content})
            if resp.stop_reason != "tool_use":
                text = "".join(b.text for b in resp.content if b.type == "text")
                return AgentResult(text, analysis, calls, tb.proposed_cases, mode=f"llm:{self.model}")
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                out = tb.run(block.name, block.input)
                calls.append({"tool": block.name, "input": block.input})
                if block.name == "analyze_bill" and isinstance(out, dict) and "error" not in out:
                    analysis = out
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": json.dumps(out, default=str)})
            messages.append({"role": "user", "content": results})

        # Step budget exhausted: fall back to the deterministic answer
        fallback = self._ask_offline(question, vkont, belnr)
        fallback.tool_calls = calls + fallback.tool_calls
        fallback.mode = "offline-fallback"
        return fallback

    # -------------------------------------------------------------- offline
    def _ask_offline(self, question, vkont, belnr) -> AgentResult:
        tb = ToolBox(self.repo)
        calls = []
        vkont = vkont or _first(ACCOUNT_RE, question)
        belnr = belnr or _first(BELNR_RE, question)
        if not vkont:
            matches = [m for w in re.findall(r"[A-Z][a-z]+", question) for m in tb.run("find_account", {"text": w})]
            calls.append({"tool": "find_account", "input": {"text": question}})
            uniq = {m["vkont"]: m for m in matches}
            if len(uniq) == 1:
                vkont = next(iter(uniq))
            else:
                names = ", ".join(f'{m["name"]} ({m["vkont"]})' for m in list(uniq.values())[:5])
                return AgentResult("Please give the contract account number." +
                                   (f" Possible matches: {names}" if names else ""), tool_calls=calls)
        a = tb.run("analyze_bill", {"vkont": vkont, "belnr": belnr})
        calls.append({"tool": "analyze_bill", "input": {"vkont": vkont, "belnr": belnr}})
        if "error" in a:
            return AgentResult(a["error"], tool_calls=calls)
        if a["primary_cause"] in ("METER_FACTOR", "ESTIMATE_CATCHUP", "LONG_PERIOD", "USAGE_SPIKE"):
            tb.run("propose_clarification_case", {
                "vkont": vkont, "belnr": a["billing_document"], "category": a["primary_cause"],
                "summary": f'{a["primary_cause_text"]}. {a["recommended_action"]}'})
            calls.append({"tool": "propose_clarification_case", "input": {"category": a["primary_cause"]}})
        return AgentResult(render_explanation(a), a, calls, tb.proposed_cases, mode="offline")


def _first(rx, text):
    m = rx.search(text or "")
    return m.group(1) if m else None


def _money(x, cur="EUR"):
    return f"{x:,.2f} {cur}"


def render_explanation(a: dict) -> str:
    cur = a["currency"]
    f = {x["cause"]: x["evidence"] for x in a["findings"]}
    cause = a["primary_cause"]
    ev = f.get(cause, {})
    head = (f'**Verdict:** {a["primary_cause_text"]}. Document {a["billing_document"]} '
            f'({a["period"]}, {a["period_days"]} days) is {_money(a["gross_amount"], cur)} '
            f'vs a typical {_money(a["typical_gross_for_same_length"], cur)} for a period this long.')

    evidence, customer = [], ""
    if cause == "METER_FACTOR":
        evidence = [f'New meter {ev["new_device_serial"]} installed on {ev["device_installed_on"]}',
                    f'Register factor changed from {ev["old_factor"]:g} to {ev["new_factor"]:g}',
                    f'Billed {ev["billed_kwh"]:,.0f} kWh vs about {ev["expected_kwh_approx"]:,.0f} kWh expected']
        customer = ("Your meter was replaced during this period and the new meter was set up incorrectly in our "
                    "system, which multiplied your usage. This bill is wrong; we will cancel and correct it.")
    elif cause == "LONG_PERIOD":
        evidence = [f'Period covers {ev["period_days"]} days instead of the usual {ev["usual_days"]}',
                    f'Daily usage {ev["daily_kwh_now"]} kWh vs {ev["daily_kwh_baseline"]} kWh usual (unchanged)']
        customer = ("This bill covers about two months because one scheduled meter reading did not take place. "
                    "Your daily usage has not changed; the amount is higher because it covers more days.")
    elif cause == "ESTIMATE_CATCHUP":
        evidence = [f'Estimated reads on {", ".join(ev["estimated_read_dates"])}',
                    f'Last actual read before that: {ev["last_actual_read"]}',
                    f'Current read: {ev["current_read_type"]}',
                    f'Approx. {ev["kwh_under_estimated_in_previous_bills_approx"]:,.0f} kWh under-billed earlier, recovered now']
        customer = ("Your previous few bills were based on estimates that were lower than your real usage. "
                    "This bill uses an actual meter reading, so it includes the usage that was not billed before. "
                    "You have not been charged twice for the same energy.")
    elif cause == "REVERSAL_REBILL":
        evidence = [f'Document {ev["reversed_document"]} ({_money(ev["reversed_amount"], cur)}) was reversed',
                    f'Valid document {ev["valid_document"]}: {_money(ev["valid_amount"], cur)}']
        customer = ("You received two bills for the same period because the first one was cancelled and corrected. "
                    "Only the corrected bill is payable.")
    elif cause == "RATE_CHANGE":
        evidence = [f'Rate category {ev["rate_category"]}: {ev["old_price_per_kwh"]} -> {ev["new_price_per_kwh"]} {cur}/kWh '
                    f'from {ev["effective_from"]} (+{ev["increase_pct"]}%)',
                    f'Extra net cost from the price change: {_money(ev["extra_net_cost"], cur)}',
                    f'Consumption vs usual: x{ev["consumption_ratio_vs_baseline"]}']
        customer = ("Your usage is about the same as usual. The bill is higher because the energy price for your "
                    "tariff increased from the date shown.")
    elif cause == "SEASONAL_HEATING":
        evidence = [f'Daily usage {ev["daily_kwh_now"]} kWh vs {ev["daily_kwh_same_period_last_year"]} kWh same period last year',
                    f'Recent months averaged {ev["daily_kwh_recent_baseline"]} kWh/day']
        customer = ("Winter usage is naturally higher with electric heating, and it matches the same month last year. "
                    "A budget billing plan can spread these costs evenly across the year.")
    elif cause == "USAGE_SPIKE":
        evidence = [f'Daily usage {ev["daily_kwh_now"]} kWh vs {ev["daily_kwh_baseline"]} kWh usual (+{ev["increase_pct"]}%)',
                    "No meter change, estimation or price change in this period"]
        if ev.get("same_period_last_year_daily"):
            evidence.append(f'Same period last year: {ev["same_period_last_year_daily"]} kWh/day')
        customer = ("Your meter recorded noticeably higher usage this period, and we found no billing or meter error. "
                    "A new appliance or a fault in the home could explain it; we can arrange a check if needed.")
    else:
        evidence = [f'Consumption vs usual: x{a["consumption_ratio_vs_baseline"]}', "No estimation, price, device or period anomalies"]
        customer = "Your bill is in line with your usual usage and current prices. No error was found."

    other = [x["cause"] for x in a["findings"][1:]]
    if other:
        evidence.append("Also detected: " + ", ".join(other))
    return "\n".join([head, "", "**Evidence:**", *[f"- {e}" for e in evidence], "",
                      f"**What to tell the customer:** {customer}", "",
                      f'**Recommended action:** {a["recommended_action"]}'])
