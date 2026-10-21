"""Read-only data access layer.

Two backends share one interface so the agent never knows where data comes from:
  * SQLiteRepository - local mock database (default, works offline)
  * ODataRepository  - RAP OData V4 service on the SAP BTP ABAP environment
                       (see abap/ folder; switch with ISU_DATA_SOURCE=odata)
"""
from __future__ import annotations

import sqlite3
from typing import Protocol

from . import config


class Repository(Protocol):
    def account(self, vkont: str) -> dict | None: ...
    def search_accounts(self, text: str) -> list[dict]: ...
    def billing_documents(self, vkont: str) -> list[dict]: ...
    def billing_lines(self, belnr: str) -> list[dict]: ...
    def meter_reads(self, vkont: str) -> list[dict]: ...
    def devices(self, vkont: str) -> list[dict]: ...
    def rates(self, tariftyp: str) -> list[dict]: ...
    def code_text(self, field: str, code: str) -> str: ...
    def create_clarification_case(self, vkont: str, belnr: str, category: str, summary: str) -> int: ...


class SQLiteRepository:
    def __init__(self, path=config.DB_PATH):
        if not path.exists():
            raise FileNotFoundError(f"Mock DB not found at {path}. Run: python -m isu_agent.cli generate")
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row

    def _all(self, sql: str, args=()) -> list[dict]:
        return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def account(self, vkont):
        rows = self._all("""
            SELECT k.vkont, b.partner, b.name, b.city, v.vertrag, v.einzdat, a.anlage, a.vstelle,
                   a.tariftyp, a.sparte
            FROM fkkvkp k JOIN but000 b ON b.partner = k.partner
                          JOIN ever v ON v.vkont = k.vkont
                          JOIN eanl a ON a.anlage = v.anlage
            WHERE k.vkont = ?""", (vkont,))
        return rows[0] if rows else None

    def search_accounts(self, text):
        like = f"%{text}%"
        return self._all("""SELECT k.vkont, b.name, b.city FROM fkkvkp k JOIN but000 b ON b.partner=k.partner
                            WHERE k.vkont LIKE ? OR b.name LIKE ? ORDER BY k.vkont LIMIT 20""", (like, like))

    def billing_documents(self, vkont):
        return self._all("""SELECT e.* FROM erch e JOIN ever v ON v.vertrag = e.vertrag
                            WHERE v.vkont = ? ORDER BY e.abrdate, e.created_on""", (vkont,))

    def billing_lines(self, belnr):
        return self._all("SELECT * FROM dberchz WHERE belnr = ? ORDER BY belzeile", (belnr,))

    def meter_reads(self, vkont):
        return self._all("""SELECT r.*, g.sernr, g.faktor FROM eabl r
                            JOIN egerh g ON g.equnr = r.equnr
                            JOIN ever v ON v.anlage = g.anlage
                            WHERE v.vkont = ? ORDER BY r.adat, r.ablesgr DESC""", (vkont,))

    def devices(self, vkont):
        return self._all("""SELECT g.* FROM egerh g JOIN ever v ON v.anlage = g.anlage
                            WHERE v.vkont = ? ORDER BY g.ab""", (vkont,))

    def rates(self, tariftyp):
        return self._all("SELECT * FROM rates WHERE tariftyp = ? ORDER BY ab", (tariftyp,))

    def code_text(self, field, code):
        rows = self._all("SELECT text FROM code_texts WHERE field=? AND code=?", (field, code))
        return rows[0]["text"] if rows else code

    def create_clarification_case(self, vkont, belnr, category, summary):
        cur = self.con.execute(
            "INSERT INTO clarif_case (vkont, belnr, category, summary, status, created_on) "
            "VALUES (?,?,?,?, 'OPEN', date('now'))", (vkont, belnr, category, summary))
        self.con.commit()
        return cur.lastrowid


class ODataRepository:
    """Reads the same entities from the RAP OData V4 service ZUI_ISU_BILLAGENT.

    Entity set and field names match abap/service/zui_isu_billagent.srvd.asddls.
    Untested until you deploy the ABAP objects on your own BTP ABAP trial.
    """

    def __init__(self, base_url=config.ODATA_BASE_URL):
        import requests  # local import keeps the SQLite path dependency-free
        if not base_url:
            raise ValueError("Set ISU_ODATA_URL to the service URL from your service binding")
        self.base = base_url.rstrip("/") + "/"
        self.s = requests.Session()
        self.s.auth = (config.ODATA_USER, config.ODATA_PASSWORD)
        self.s.headers["Accept"] = "application/json"

    def _get(self, entity: str, flt: str = "", orderby: str = "") -> list[dict]:
        params = {}
        if flt:
            params["$filter"] = flt
        if orderby:
            params["$orderby"] = orderby
        r = self.s.get(self.base + entity, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("value", [])

    # OData entities use CamelCase aliases; map them back to the IS-U style keys
    _MAP = {
        "ContractAccount": "vkont", "BusinessPartner": "partner", "PartnerName": "name", "City": "city",
        "Contract": "vertrag", "MoveInDate": "einzdat", "Installation": "anlage", "Premise": "vstelle",
        "RateCategory": "tariftyp", "Division": "sparte", "BillingDocument": "belnr",
        "PeriodStart": "abrdats", "PeriodEnd": "abrdate", "ConsumptionKwh": "kwh", "NetAmount": "net_amount",
        "VatAmount": "vat_amount", "GrossAmount": "gross_amount", "Currency": "waers",
        "ReversalIndicator": "stokz", "ReversedBy": "reversed_by", "CreatedOn": "created_on",
        "LineNumber": "belzeile", "LineType": "line_type", "ValidFrom": "ab", "ValidTo": "bis",
        "Quantity": "quantity", "Unit": "unit", "Price": "price", "Amount": "amount",
        "MeterReadDocument": "ablbelnr", "Device": "equnr", "ReadDate": "adat", "Reading": "zwstand",
        "ReadType": "istablart", "ReadReason": "ablesgr", "SerialNumber": "sernr", "Factor": "faktor",
        "EnergyPrice": "energy_price",
    }

    _NUMERIC = {"kwh", "net_amount", "vat_amount", "gross_amount", "quantity", "price", "amount",
                "zwstand", "faktor", "energy_price"}

    def _conv(self, rows):
        out = []
        for r in rows:
            row = {self._MAP.get(k, k): v for k, v in r.items() if not k.startswith("@")}
            for k in self._NUMERIC & row.keys():
                row[k] = float(row[k]) if row[k] not in (None, "") else 0.0
            for k in ("stokz", "reversed_by"):
                if k in row and row[k] is None:
                    row[k] = ""
            out.append(row)
        return out

    def account(self, vkont):
        rows = self._conv(self._get("Account", f"ContractAccount eq '{vkont}'"))
        return rows[0] if rows else None

    def search_accounts(self, text):
        return self._conv(self._get("Account", f"contains(PartnerName,'{text}') or ContractAccount eq '{text}'"))

    def billing_documents(self, vkont):
        return self._conv(self._get("BillingDocument", f"ContractAccount eq '{vkont}'", "PeriodEnd,CreatedOn"))

    def billing_lines(self, belnr):
        return self._conv(self._get("BillingLine", f"BillingDocument eq '{belnr}'", "LineNumber"))

    def meter_reads(self, vkont):
        return self._conv(self._get("MeterRead", f"ContractAccount eq '{vkont}'", "ReadDate"))

    def devices(self, vkont):
        return self._conv(self._get("DeviceHistory", f"ContractAccount eq '{vkont}'", "ValidFrom"))

    def rates(self, tariftyp):
        return self._conv(self._get("RatePrice", f"RateCategory eq '{tariftyp}'", "ValidFrom"))

    def code_text(self, field, code):
        texts = {("ISTABLART", "01"): "Meter read by utility", ("ISTABLART", "02"): "Meter read by customer",
                 ("ISTABLART", "03"): "Automatic estimation", ("ABLESGR", "01"): "Periodic meter reading",
                 ("ABLESGR", "21"): "Meter reading at device installation",
                 ("ABLESGR", "22"): "Meter reading at device removal"}
        return texts.get((field, code), code)

    def create_clarification_case(self, vkont, belnr, category, summary):
        r = self.s.get(self.base, headers={"x-csrf-token": "fetch"}, timeout=30)
        token = r.headers.get("x-csrf-token", "")
        body = {"ContractAccount": vkont, "BillingDocument": belnr, "Category": category, "Summary": summary}
        r = self.s.post(self.base + "ClarificationCase", json=body,
                        headers={"x-csrf-token": token, "Content-Type": "application/json"}, timeout=30)
        r.raise_for_status()
        return r.json().get("CaseUuid")


def get_repository() -> Repository:
    return ODataRepository() if config.DATA_SOURCE == "odata" else SQLiteRepository()
