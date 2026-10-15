import asyncio

from app.agents.ledger_reader import LedgerLine, LedgerReading, read_ledger_page


def test_amounts_are_parsed_by_code_not_the_model(fake_gemini):
    lines, model = asyncio.run(read_ledger_page(fake_gemini, b"fake-image", "image/jpeg"))

    assert model == "gemini-test"
    assert [line.amount_rp for line in lines] == [610_000, 2_100_000, 20_000, None]
    assert lines[1].amount_text == "2,1jt"  # the raw text is kept for the evidence viewer


def test_asks_gemini_for_the_ledger_schema(fake_gemini):
    asyncio.run(read_ledger_page(fake_gemini, b"fake-image", "image/png", variant=1))

    call = fake_gemini.calls[0]
    assert call["schema"] is LedgerReading
    assert "Never calculate" in call["system"]
    assert call["contents"][0].inline_data.mime_type == "image/png"


def test_keeps_a_crossed_out_amount_apart_from_the_final_one(fake_gemini):
    fake_gemini.reading = LedgerReading(
        legible=True,
        lines=[
            LedgerLine(
                line=1,
                description="belanja agen",
                amount_text="1,5jt",
                crossed_out_text="1,8jt",
                kind="purchase",
                confidence=0.9,
            )
        ],
    )

    lines, _ = asyncio.run(read_ledger_page(fake_gemini, b"img", "image/jpeg"))

    assert lines[0].amount_rp == 1_500_000
    assert lines[0].crossed_out_text == "1,8jt"
