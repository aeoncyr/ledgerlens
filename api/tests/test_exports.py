"""Exports of a credit file: only the lender's side may download them, in JSON or CSV."""

import csv
import io

import pytest

APP_ID = "app12345xyz"

MEMO = {
    "assessment": "partially_verified",
    "policy": {
        "evidenceStrength": 62,
        "maxInstallment": 900_000,
        "requestedInstallment": 870_000,
        "withinPolicy": True,
        "reasons": [],
    },
    "cashflow": {"revenueLow": 9_000_000, "revenueHigh": 12_000_000, "months": []},
    "findings": [
        {
            "kind": "discrepancy",
            "severity": "high",
            "text": '=HYPERLINK("x") notebook sales run above QRIS',
            "citations": [{"evidenceId": "ev-1", "locator": "page 2, line 4"}],
            "resolved": False,
            "answer": None,
        }
    ],
    "confirmations": [],
    "memo": {
        "headline": "Sales are mostly proven",
        "character": {"text": "Six years trading", "citations": []},
        "capacity": {"text": "Within policy", "citations": []},
        "officerNextSteps": ["Visit the stall"],
    },
    "facts": [{"key": "max_installment", "label": "Largest instalment", "value": 900_000}],
    "models": ["gemini-test"],
}


@pytest.fixture
def stored(fake_db):
    fake_db.docs[("applications", APP_ID)] = {
        "officerUid": "officer-1",
        "ownerUid": "owner-1",
        "reviewerUid": "reviewer-1",
        "business": {"alias": "Warung Bu Sari", "type": "grocery", "city": "Bekasi"},
        "request": {"amount": 10_000_000, "tenorMonths": 12},
        "status": "ready",
        "decision": {"action": "approve", "reason": "Cash flow supports it"},
    }
    fake_db.docs[("applications", APP_ID, "memo", "current")] = dict(MEMO)
    fake_db.docs[("applications", APP_ID, "evidence", "ev-1")] = {
        "type": "ledger_page",
        "label": "Notebook page 2",
        "submittedBy": "owner",
    }
    return fake_db


@pytest.mark.parametrize("fmt", ["json", "csv"])
def test_only_the_lenders_side_can_export(client_as, anonymous_client, stored, fmt):
    path = f"/api/applications/{APP_ID}/export.{fmt}"

    assert client_as("officer-1").get(path).status_code == 200
    assert client_as("reviewer-1").get(path).status_code == 200
    assert client_as("owner-1").get(path).status_code == 404
    assert client_as("stranger").get(path).status_code == 404
    assert anonymous_client.get(path).status_code == 401


def test_export_needs_an_analysis(client_as, stored):
    del stored.docs[("applications", APP_ID, "memo", "current")]

    assert client_as("officer-1").get(f"/api/applications/{APP_ID}/export.json").status_code == 409


def test_the_json_export_carries_findings_with_their_citations(client_as, stored):
    response = client_as("officer-1").get(f"/api/applications/{APP_ID}/export.json")

    assert "attachment" in response.headers["content-disposition"]
    exported = response.json()
    assert exported["format"] == "ledgerlens.credit-file/v1"
    assert exported["business"]["alias"] == "Warung Bu Sari"
    assert exported["request"] == {"amountRp": 10_000_000, "tenorMonths": 12}
    assert exported["policy"]["maxInstallment"] == 900_000
    citation = exported["findings"][0]["citations"][0]
    assert citation == {
        "evidenceId": "ev-1",
        "evidenceLabel": "Notebook page 2",
        "locator": "page 2, line 4",
    }
    assert exported["evidence"][0]["tier"] == "soft"
    assert exported["decision"]["action"] == "approve"
    assert exported["memo"]["officerNextSteps"] == ["Visit the stall"]


def test_the_csv_has_a_summary_row_and_a_row_per_finding(client_as, stored):
    response = client_as("officer-1").get(f"/api/applications/{APP_ID}/export.csv")

    assert response.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))
    summary = dict(zip(rows[0], rows[1], strict=True))
    assert summary["Business"] == "Warung Bu Sari"
    assert summary["Largest instalment the policy allows (Rp)"] == "900000"
    assert summary["Within policy"] == "yes"
    assert rows[2] == []
    assert rows[3][:4] == ["#", "Severity", "Kind", "Finding"]
    finding = rows[4]
    # Text that would run as a formula in Excel or Sheets is quoted.
    assert finding[3].startswith("'=HYPERLINK")
    assert finding[4] == "Notebook page 2, page 2, line 4"
