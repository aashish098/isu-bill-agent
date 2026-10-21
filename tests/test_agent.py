"""Run with: python -m pytest -q"""
import json

import pytest

from isu_agent import config
from isu_agent.agent import BillAgent
from isu_agent.mockdata import generate
from isu_agent.repository import SQLiteRepository
from isu_agent.rules import analyze_bill


@pytest.fixture(scope="session")
def repo():
    if not config.DB_PATH.exists():
        generate()
    return SQLiteRepository()


@pytest.fixture(scope="session")
def truth():
    return json.loads(config.GROUND_TRUTH_PATH.read_text())


def test_every_planted_scenario_is_detected(repo, truth):
    for g in truth:
        assert analyze_bill(repo, g["vkont"], g["focus_belnr"])["primary_cause"] == g["scenario"], g


def test_no_false_positives_on_normal_accounts(repo, truth):
    for g in [t for t in truth if t["scenario"] == "NORMAL"]:
        docs = [d for d in repo.billing_documents(g["vkont"]) if d["stokz"] != "X"][6:]
        for d in docs:
            assert analyze_bill(repo, g["vkont"], d["belnr"])["primary_cause"] == "NORMAL"


def test_reversed_document_resolves_to_rebill(repo, truth):
    g = next(t for t in truth if t["scenario"] == "REVERSAL_REBILL")
    res = analyze_bill(repo, g["vkont"], g["reversed_belnr"])
    assert res["billing_document"] == g["focus_belnr"]


def test_offline_agent_proposes_but_never_writes(repo, truth):
    g = next(t for t in truth if t["scenario"] == "METER_FACTOR")
    before = repo.con.execute("SELECT COUNT(*) FROM clarif_case").fetchone()[0]
    res = BillAgent(repo, provider="offline").ask(g["question"], g["vkont"])
    after = repo.con.execute("SELECT COUNT(*) FROM clarif_case").fetchone()[0]
    assert res.proposed_cases and before == after
    assert "factor" in res.answer.lower()


def test_unknown_account(repo):
    assert "error" in analyze_bill(repo, "999999999999")
