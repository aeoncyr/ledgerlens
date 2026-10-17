"""The whole pipeline offline: scripted Gemini answers in, findings, outcome and memo out."""

import asyncio
import dataclasses
from datetime import UTC, datetime

from app.agents.ledger_reader import LedgerLine, LedgerReading
from app.agents.memo_writer import MemoDraft, MemoSection, OwnerSummary
from app.agents.qris_reader import QrisReading, QrisRow, QrisTotal
from app.agents.receipt_reader import ReceiptItem, ReceiptReading
from app.agents.verifier import CitationOut, Confirmation, Verification, VerifierFinding
from app.analysis.pipeline import Application, EvidenceItem, judge, reconcile, run_pipeline
from app.schemas import Assessment, EvidenceType, Finding, LedgerLineOut

CAPTURED = datetime(2026, 10, 6, 9, 0, tzinfo=UTC)

PAGE = LedgerReading(
    legible=True,
    lines=[
        LedgerLine(line=1, description="Sep 1-10", kind="other", confidence=0.99),
        LedgerLine(
            line=2,
            date_text="1/9",
            description="laku",
            amount_text="9jt",
            kind="sale",
            confidence=0.95,
        ),
        LedgerLine(
            line=3,
            description="belanja agen",
            amount_text="4jt",
            kind="purchase",
            confidence=0.9,
        ),
    ],
)
RECEIPT = ReceiptReading(
    legible=True,
    merchant="Agen Sembako Makmur",
    date_text="2/9/26",
    items=[ReceiptItem(name="beras", amount_text="4.000.000", confidence=0.9)],
    total_text="4.000.000",
    handwritten=True,
)
QRIS = QrisReading(
    legible=True,
    app_name="Dompet Usaha",
    rows=[
        QrisRow(
            row=1, date_text="30 Sep 2026", amount_text="+Rp25.000", direction="in", confidence=0.99
        )
    ],
    totals=[QrisTotal(period_text="September 2026", amount_text="Rp3.000.000")],
    is_screenshot=True,
)


def section(text: str) -> MemoSection:
    return MemoSection(text=text, citations=[])


class ScriptedGemini:
    """Answers each agent by the schema it asks for, and records what it was asked."""

    def __init__(self, verification: Verification, memo: MemoDraft) -> None:
        self.answers = {
            LedgerReading: PAGE,
            ReceiptReading: RECEIPT,
            QrisReading: QRIS,
            Verification: verification,
            MemoDraft: memo,
        }
        self.calls: list[type] = []
        self.roles: dict[type, str] = {}
        self.contents: dict[type, list] = {}

    async def generate(self, *, contents, schema, system, temperature=0.0, attempts=3, role="read"):
        self.calls.append(schema)
        self.roles[schema] = role
        self.contents[schema] = contents
        return self.answers[schema], "gemini-test"


class BytesStore:
    async def read(self, path: str) -> tuple[bytes, str]:
        return b"image", "image/jpeg"


APPLICATION = Application(
    alias="Warung Uji",
    business_type="Grocery stall",
    city="Bekasi",
    years_operating=5,
    amount=10_000_000,
    tenor_months=12,
)
ITEMS = [
    EvidenceItem("ev-page", EvidenceType.LEDGER_PAGE, "page.jpg", CAPTURED),
    EvidenceItem("ev-receipt", EvidenceType.RECEIPT, "receipt.jpg", CAPTURED),
    EvidenceItem("ev-qris", EvidenceType.QRIS_HISTORY, "qris.png", CAPTURED),
]
MEMO = MemoDraft(
    headline="Sources agree; capacity is [[revenue_low]] to [[revenue_high]] a month.",
    character=section("Five years operating."),
    capacity=section("The policy allows up to [[max_installment]] a month."),
    capital=section("Stock is restocked weekly."),
    collateral=section("None needed under [[kur_collateral_free_limit]]."),
    conditions=section("Working capital."),
    officer_next_steps=["Confirm the market-day sales."],
    owner_summary=OwnerSummary(
        verified="Penjualan cocok.",
        missing="Tidak ada.",
        tips=["Simpan nota."],
        verified_en="Sales match.",
        missing_en="Nothing.",
        tips_en=["Keep your receipts."],
    ),
)


def run(verification: Verification, memo: MemoDraft = MEMO, application: Application = APPLICATION):
    gemini = ScriptedGemini(verification, memo)
    steps = []

    async def progress(agent, message, state, detail=None):
        steps.append((agent, state, message))

    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=application,
            items=list(ITEMS),
            progress=progress,
        )
    )
    return result, gemini, steps


def test_other_monthly_debts_reach_the_policy_and_the_verifier():
    with_debt = dataclasses.replace(APPLICATION, existing_monthly_debt=450_000)
    result, gemini, _ = run(Verification(findings=[], confirmations=[]), application=with_debt)
    without, _, _ = run(Verification(findings=[], confirmations=[]))

    assert result.policy.max_installment == without.policy.max_installment - 450_000
    case_file = gemini.contents[Verification][0]
    assert '"other_monthly_loan_instalments": "[[existing_monthly_debt]]"' in case_file
    assert "Rp 450.000" in case_file
    debt = next(f for f in result.facts if f["key"] == "existing_monthly_debt")
    assert debt["value"] == 450_000


def test_the_stress_test_is_a_figure_the_memo_can_cite():
    result, _, _ = run(Verification(findings=[], confirmations=[]))

    assert result.policy.within_policy
    stress = next(f for f in result.facts if f["key"] == "stress_drop_pct")
    assert stress["value"] == result.policy.stress_drop_pct / 100
    assert stress["display"] == f"{result.policy.stress_drop_pct}%"


def test_runs_every_agent_and_computes_cash_flow_in_code():
    result, gemini, steps = run(Verification(findings=[], confirmations=[]))

    assert gemini.calls.count(LedgerReading) == 2  # the page is read twice
    assert gemini.calls[-2:] == [Verification, MemoDraft]
    assert gemini.roles == {
        LedgerReading: "read",
        ReceiptReading: "read",
        QrisReading: "read",
        Verification: "write",
        MemoDraft: "write",
    }
    month = result.cashflow.months[0]
    assert (month.month, month.claimed_sales, month.proven_inflows, month.receipt_purchases) == (
        "2026-09",
        9_000_000,
        3_000_000,
        4_000_000,
    )
    assert result.assessment is Assessment.VERIFIED
    assert ("memo_writer", "done", "Credit memo ready") in steps


def test_memo_figures_are_filled_in_by_code():
    result, _, _ = run(Verification(findings=[], confirmations=[]))

    assert result.memo["headline"] == (
        "Sources agree; capacity is Rp 3.000.000 to Rp 9.000.000 a month."
    )
    assert "max_installment" in result.memo["figures"]


def test_code_checks_keep_their_severity_even_if_the_verifier_softens_them():
    qris = QRIS.model_copy(
        update={
            "rows": [
                QrisRow(
                    row=1,
                    amount_text="+Rp5.000.000",
                    direction="in",
                    date_text="30 Sep 2026",
                    confidence=0.9,
                )
            ]
        }
    )
    verification = Verification(
        findings=[
            VerifierFinding(
                check_id="check-1",
                kind="low_confidence",
                severity="low",
                text="The rows exceed the monthly total.",
                citations=[CitationOut(evidence_id="ev-qris", locator="row 1")],
                follow_up_question="Boleh kami lihat riwayat di aplikasinya, Bu?",
            )
        ],
        confirmations=[Confirmation(text="Receipts match purchases.", citations=[])],
    )
    gemini = ScriptedGemini(verification, MEMO)
    gemini.answers[QrisReading] = qris

    async def progress(*_, **__):
        pass

    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=APPLICATION,
            items=list(ITEMS),
            progress=progress,
        )
    )

    finding = result.findings[0]
    assert (finding.kind, finding.severity, finding.source) == ("fraud_signal", "high", "code")
    assert finding.follow_up_question == "Boleh kami lihat riwayat di aplikasinya, Bu?"
    assert result.assessment is Assessment.INCONSISTENT


def test_an_edited_qris_total_is_caught_and_only_its_listed_rows_count():
    def row(n, amount_text):
        return QrisRow(
            row=n, date_text="30 Sep 2026", amount_text=amount_text, direction="in", confidence=0.99
        )

    # Both transactions of the month are listed, but the printed total was raised by Rp 5.000.000.
    edited = QRIS.model_copy(
        update={
            "rows": [row(1, "+Rp250.000"), row(2, "+Rp1.750.000")],
            "totals": [
                QrisTotal(
                    period_text="September 2026",
                    amount_text="Rp7.000.000",
                    count_text="2 transaksi",
                )
            ],
        }
    )
    gemini = ScriptedGemini(Verification(findings=[], confirmations=[]), MEMO)
    gemini.answers[QrisReading] = edited

    async def progress(*_, **__):
        pass

    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=APPLICATION,
            items=list(ITEMS),
            progress=progress,
        )
    )

    finding = next(f for f in result.findings if f.kind == "fraud_signal")
    assert finding.severity == "high"
    assert "add up to Rp 2.000.000, not the printed total of Rp 7.000.000" in finding.text
    assert "Only its listed rows, Rp 2.000.000, count as money received." in finding.text
    assert result.cashflow.months[0].proven_inflows == 2_000_000
    assert result.assessment is Assessment.INCONSISTENT


def test_numbers_the_verifier_invents_are_removed():
    made_up = Verification(
        findings=[
            VerifierFinding(
                kind="discrepancy",
                severity="low",
                text="Sales look like Rp 12.500.000 a month.",
                citations=[CitationOut(evidence_id="ev-page", locator="line 2")],
            )
        ],
        confirmations=[],
    )

    result, gemini, _ = run(made_up)

    assert gemini.calls.count(Verification) == 2  # asked once more, with the problem spelled out
    assert result.findings[0].text == "Sales look like Rp [figure removed] a month."
    assert result.figure_problems


def test_a_reader_failure_becomes_a_finding_not_a_crash():
    class FlakyStore(BytesStore):
        async def read(self, path):
            if path == "receipt.jpg":
                raise OSError("file missing")
            return await super().read(path)

    async def progress(*_, **__):
        pass

    gemini = ScriptedGemini(Verification(findings=[], confirmations=[]), MEMO)
    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=FlakyStore(),
            application=APPLICATION,
            items=list(ITEMS),
            progress=progress,
        )
    )

    assert result.unreadable == ["Receipt 1"]
    assert any(f.kind == "missing_evidence" for f in result.findings)


def test_reconcile_marks_lines_where_the_two_readings_disagree():
    def line(n, amount):
        return LedgerLineOut(
            line=n,
            date_text=None,
            description="jual",
            amount_text="x",
            amount_rp=amount,
            kind="sale",
            confidence=0.95,
        )

    lines, disagreements = reconcile(
        [line(1, 500_000), line(2, 75_000)], [line(1, 500_000), line(2, 15_000)]
    )

    assert disagreements == [(2, 75_000, 15_000)]
    assert lines[1].confidence == 0.5
    assert lines[0].confidence == 0.95


def test_reconcile_tolerates_readings_that_number_lines_differently():
    def line(n, amount):
        return LedgerLineOut(
            line=n,
            date_text=None,
            description="jual",
            amount_text="x",
            amount_rp=amount,
            kind="sale",
            confidence=0.95,
        )

    first = [line(2, 500_000), line(3, 610_000), line(4, 75_000)]
    shifted = [line(1, 500_000), line(2, 610_000), line(3, 75_000)]  # heading skipped

    lines, disagreements = reconcile(first, shifted)

    assert disagreements == []
    assert all(x.confidence == 0.95 for x in lines)


def test_a_single_read_saves_calls_on_the_free_tier():
    gemini = ScriptedGemini(Verification(findings=[], confirmations=[]), MEMO)

    async def progress(*_, **__):
        pass

    asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=APPLICATION,
            items=list(ITEMS),
            progress=progress,
            max_parallel=2,
            double_read=False,
        )
    )

    assert gemini.calls.count(LedgerReading) == 1


def test_an_answer_resolves_a_question_but_not_a_material_contradiction():
    first, gemini, _ = run(Verification(findings=[], confirmations=[]))
    context = first.context.model_copy(
        update={
            "checks": {
                "check-1": first.context.checks.get("check-1")
                or Finding(kind="discrepancy", severity="high", source="code", text="5.6x")
            }
        }
    )
    answers = [
        {"finding": "Saturday sales", "question": "Kenapa?", "answer": "Sabtu hari pasar."},
        {"finding": "5.6x", "question": "Kenapa?", "answer": "Beli bahan tanpa nota."},
    ]
    gemini.answers[Verification] = Verification(
        findings=[
            VerifierFinding(
                kind="discrepancy",
                severity="medium",
                text="Saturday sales are higher.",
                citations=[],
                resolved=True,
                answered_by=1,
            ),
            VerifierFinding(
                check_id="check-1",
                kind="discrepancy",
                severity="low",
                text="Sales are high.",
                citations=[],
                resolved=True,
                answered_by=2,
            ),
        ],
        confirmations=[],
    )

    async def progress(*_, **__):
        pass

    result = asyncio.run(judge(gemini=gemini, context=context, progress=progress, answers=answers))

    by_text = {f.text: f for f in result.findings}
    assert by_text["Saturday sales are higher."].resolved is True
    assert by_text["Saturday sales are higher."].answer == "Sabtu hari pasar."
    material = by_text["Sales are high."]
    assert (material.severity, material.resolved) == ("high", False)
    assert material.answer == "Beli bahan tanpa nota."
    assert result.assessment is Assessment.INCONSISTENT


def test_qris_only_the_owner_sent_needs_an_officer_to_confirm_it():
    gemini = ScriptedGemini(Verification(findings=[], confirmations=[]), MEMO)
    items = [
        EvidenceItem(
            "ev-page", EvidenceType.LEDGER_PAGE, "page.jpg", CAPTURED, submitted_by="owner"
        ),
        EvidenceItem(
            "ev-receipt", EvidenceType.RECEIPT, "receipt.jpg", CAPTURED, submitted_by="owner"
        ),
        EvidenceItem(
            "ev-qris", EvidenceType.QRIS_HISTORY, "qris.png", CAPTURED, submitted_by="owner"
        ),
    ]

    async def progress(*_, **__):
        pass

    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=APPLICATION,
            items=items,
            progress=progress,
        )
    )

    assert any("sent by the owner" in f.text for f in result.findings)
    assert result.assessment is Assessment.PARTIALLY_VERIFIED


def test_a_confirmed_reading_changes_the_cash_flow_and_settles_the_dispute():
    from app.analysis.pipeline import apply_confirmations
    from app.tools.cashflow import Entry
    from app.tools.facts import FactTable
    from app.tools.policy import LenderPolicy

    first, _, _ = run(Verification(findings=[], confirmations=[]))
    dispute = Finding(kind="low_confidence", severity="low", source="code", text="Readings differ.")
    context = first.context.model_copy(
        update={
            "entries": [
                Entry(
                    month="2026-09",
                    kind="sale",
                    amount_rp=850_000,
                    evidence_type=EvidenceType.LEDGER_PAGE,
                    evidence_id="ev-page",
                    locator="line 2",
                ),
            ],
            "checks": {**first.context.checks, "check-99": dispute},
            "disputes": {"check-99": {"evidence_id": "ev-page", "lines": [2]}},
            "confirmed": {"ev-page": {"2": 650_000}},
        }
    )
    facts = FactTable.from_facts(context.facts)

    summary, checks = apply_confirmations(context, facts, APPLICATION, LenderPolicy())

    assert summary.avg_claimed_sales == 650_000
    assert "check-99" not in checks
    assert facts.render("[[avg_claimed_sales]]") == "Rp 650.000"
