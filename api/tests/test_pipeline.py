"""The whole pipeline offline: scripted Gemini answers in, findings, outcome and memo out."""

import asyncio
from datetime import UTC, datetime

from app.agents.ledger_reader import LedgerLine, LedgerReading
from app.agents.memo_writer import MemoDraft, MemoSection, OwnerSummary
from app.agents.qris_reader import QrisReading, QrisRow, QrisTotal
from app.agents.receipt_reader import ReceiptItem, ReceiptReading
from app.agents.verifier import CitationOut, Confirmation, Verification, VerifierFinding
from app.analysis.pipeline import Application, EvidenceItem, reconcile, run_pipeline
from app.schemas import Assessment, EvidenceType, LedgerLineOut

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

    async def generate(self, *, contents, schema, system, temperature=0.0, attempts=3):
        self.calls.append(schema)
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
        verified="Penjualan cocok.", missing="Tidak ada.", tips=["Simpan nota."]
    ),
)


def run(verification: Verification, memo: MemoDraft = MEMO):
    gemini = ScriptedGemini(verification, memo)
    steps = []

    async def progress(agent, message, state):
        steps.append((agent, state, message))

    result = asyncio.run(
        run_pipeline(
            gemini=gemini,
            store=BytesStore(),
            application=APPLICATION,
            items=list(ITEMS),
            progress=progress,
        )
    )
    return result, gemini, steps


def test_runs_every_agent_and_computes_cash_flow_in_code():
    result, gemini, steps = run(Verification(findings=[], confirmations=[]))

    assert gemini.calls.count(LedgerReading) == 2  # the page is read twice
    assert gemini.calls[-2:] == [Verification, MemoDraft]
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

    async def progress(*_):
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

    async def progress(*_):
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
