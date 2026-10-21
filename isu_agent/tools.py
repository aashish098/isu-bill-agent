"""Tools exposed to the LLM agent. All are read-only except the draft case,
which only *proposes* a clarification case; a human must approve it in the UI/CLI."""
from __future__ import annotations

from .rules import analyze_bill

TOOL_SPECS = [
    {
        "name": "find_account",
        "description": "Search contract accounts by customer name or contract account number. Use when the user gives a name instead of an account number.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "get_account_overview",
        "description": "Customer master data for a contract account: business partner, contract, installation, premise, rate category.",
        "input_schema": {"type": "object", "properties": {"vkont": {"type": "string"}}, "required": ["vkont"]},
    },
    {
        "name": "get_billing_documents",
        "description": "Billing documents (ERCH) for the account, oldest first. Includes period, kWh, amounts and reversal indicator (stokz='X').",
        "input_schema": {"type": "object", "properties": {
            "vkont": {"type": "string"}, "last_n": {"type": "integer", "description": "Only the most recent N documents (default 13)"}},
            "required": ["vkont"]},
    },
    {
        "name": "get_billing_lines",
        "description": "Line items (DBERCHZ) of one billing document: energy lines with price, fixed charge, VAT.",
        "input_schema": {"type": "object", "properties": {"belnr": {"type": "string"}}, "required": ["belnr"]},
    },
    {
        "name": "get_meter_reads",
        "description": "Meter reading results (EABL) with read type text (actual/customer/estimated) and read reason, plus device serial and factor.",
        "input_schema": {"type": "object", "properties": {
            "vkont": {"type": "string"}, "last_n": {"type": "integer", "description": "Most recent N reads (default 8)"}},
            "required": ["vkont"]},
    },
    {
        "name": "get_device_history",
        "description": "Device installation history (EGERH-like): serial numbers, validity dates and register multiplication factor.",
        "input_schema": {"type": "object", "properties": {"vkont": {"type": "string"}}, "required": ["vkont"]},
    },
    {
        "name": "get_rate_history",
        "description": "Energy price history for a rate category (tariftyp).",
        "input_schema": {"type": "object", "properties": {"tariftyp": {"type": "string"}}, "required": ["tariftyp"]},
    },
    {
        "name": "analyze_bill",
        "description": "Run the deterministic anomaly checks for a billing document (latest valid one if belnr omitted). Returns primary cause, findings with evidence and recommended action. ALWAYS call this before concluding.",
        "input_schema": {"type": "object", "properties": {"vkont": {"type": "string"}, "belnr": {"type": "string"}},
                         "required": ["vkont"]},
    },
    {
        "name": "propose_clarification_case",
        "description": "Propose (not create) a clarification case for a human agent to approve. Use only when a correction or follow-up is needed.",
        "input_schema": {"type": "object", "properties": {
            "vkont": {"type": "string"}, "belnr": {"type": "string"},
            "category": {"type": "string", "description": "Primary cause code from analyze_bill"},
            "summary": {"type": "string", "description": "One or two sentences for the back-office team"}},
            "required": ["vkont", "belnr", "category", "summary"]},
    },
]


class ToolBox:
    def __init__(self, repo):
        self.repo = repo
        self.proposed_cases: list[dict] = []

    def run(self, name: str, args: dict):
        fn = getattr(self, f"_t_{name}", None)
        if fn is None:
            return {"error": f"Unknown tool {name}"}
        try:
            return fn(**args)
        except Exception as exc:  # surface errors to the model instead of crashing
            return {"error": f"{type(exc).__name__}: {exc}"}

    def _t_find_account(self, text):
        return self.repo.search_accounts(text)

    def _t_get_account_overview(self, vkont):
        return self.repo.account(vkont) or {"error": "not found"}

    def _t_get_billing_documents(self, vkont, last_n=13):
        return self.repo.billing_documents(vkont)[-last_n:]

    def _t_get_billing_lines(self, belnr):
        return self.repo.billing_lines(belnr)

    def _t_get_meter_reads(self, vkont, last_n=8):
        rows = self.repo.meter_reads(vkont)[-last_n:]
        for r in rows:
            r["read_type_text"] = self.repo.code_text("ISTABLART", r["istablart"])
            r["read_reason_text"] = self.repo.code_text("ABLESGR", r["ablesgr"])
        return rows

    def _t_get_device_history(self, vkont):
        return self.repo.devices(vkont)

    def _t_get_rate_history(self, tariftyp):
        return self.repo.rates(tariftyp)

    def _t_analyze_bill(self, vkont, belnr=None):
        return analyze_bill(self.repo, vkont, belnr)

    def _t_propose_clarification_case(self, vkont, belnr, category, summary):
        case = {"vkont": vkont, "belnr": belnr, "category": category, "summary": summary}
        self.proposed_cases.append(case)
        return {"status": "PROPOSED", "note": "Awaiting human approval; nothing was written to SAP.", **case}
