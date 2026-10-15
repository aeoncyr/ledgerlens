import asyncio

from app.agents.receipt_reader import ReceiptItem, ReceiptReading, read_receipt


def reading(**overrides) -> ReceiptReading:
    fields = {
        "legible": True,
        "merchant": "Toko Sumber Rejeki",
        "date_text": "12/09/26",
        "items": [
            ReceiptItem(
                name="Beras 25kg", quantity_text="2", amount_text="640.000", confidence=0.95
            ),
            ReceiptItem(name="Minyak 2L", quantity_text="6", amount_text="210rb", confidence=0.9),
        ],
        "subtotal_text": "850.000",
        "discount_text": "-10.000",
        "total_text": "Rp 840.000",
        "handwritten": True,
    }
    return ReceiptReading(**(fields | overrides))


def test_parses_amounts_and_adds_up_items_in_code(fake_gemini):
    fake_gemini.reading = reading()

    receipt, model = asyncio.run(read_receipt(fake_gemini, b"img", "image/jpeg"))

    assert model == "gemini-test"
    assert [item.amount_rp for item in receipt.items] == [640_000, 210_000]
    assert receipt.items_sum_rp == 850_000
    assert receipt.subtotal_rp == 850_000
    assert receipt.discount_rp == 10_000
    assert receipt.total_rp == 840_000
    assert fake_gemini.calls[0]["schema"] is ReceiptReading


def test_leaves_the_sum_empty_when_an_item_cannot_be_parsed(fake_gemini):
    fake_gemini.reading = reading(
        items=[ReceiptItem(name="Gula", amount_text="??", confidence=0.3)]
    )

    receipt, _ = asyncio.run(read_receipt(fake_gemini, b"img", "image/jpeg"))

    assert receipt.items[0].amount_rp is None
    assert receipt.items_sum_rp is None


def test_reads_a_discount_in_brackets(fake_gemini):
    fake_gemini.reading = reading(discount_text="(5.000)")

    receipt, _ = asyncio.run(read_receipt(fake_gemini, b"img", "image/jpeg"))

    assert receipt.discount_rp == 5_000
