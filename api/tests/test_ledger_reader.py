import asyncio

from app.agents.ledger_reader import LedgerReading, read_ledger_page


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
