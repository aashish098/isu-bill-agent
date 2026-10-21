"""Central configuration for the IS-U Bill Anomaly Explainer POC."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = Path(os.getenv("ISU_DB_PATH", DATA_DIR / "isu_mock.db"))
GROUND_TRUTH_PATH = ROOT / "eval" / "ground_truth.json"

# Commercial settings used by the mock billing engine
CURRENCY = "EUR"
VAT_RATE = 0.19          # German VAT, applied to net amount
FIXED_CHARGE_PER_DAY = 0.40

# Data source: "sqlite" (default, local mock) or "odata" (BTP ABAP environment)
DATA_SOURCE = os.getenv("ISU_DATA_SOURCE", "sqlite")
ODATA_BASE_URL = os.getenv("ISU_ODATA_URL", "")      # e.g. https://<host>/sap/opu/odata4/sap/zui_isu_billagent_o4/srvd/sap/zui_isu_billagent/0001/
ODATA_USER = os.getenv("ISU_ODATA_USER", "")
ODATA_PASSWORD = os.getenv("ISU_ODATA_PASSWORD", "")

# LLM settings ("offline" uses the deterministic explainer, no API key needed)
LLM_PROVIDER = os.getenv("ISU_LLM_PROVIDER", "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "offline")
LLM_MODEL = os.getenv("ISU_LLM_MODEL", "claude-sonnet-5-5")
MAX_AGENT_STEPS = int(os.getenv("ISU_MAX_AGENT_STEPS", "8"))

# Detection thresholds
LONG_PERIOD_DAYS = 40
SPIKE_RATIO = 1.30
RATE_INCREASE_PCT = 5.0
SEASONAL_TOLERANCE = (0.80, 1.25)
