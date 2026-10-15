from app.agents.receipt_reader import ReceiptItem, ReceiptReading


def test_reads_a_page_and_stores_the_result(client, fake_db):
    response = client.post(
        "/api/readings/ledger-page",
        files={"file": ("page.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["model"] == "gemini-test"
    assert body["lines"][1]["amountRp"] == 2_100_000
    stored = fake_db.collections["pageReadings"][body["readingId"]]
    assert stored["uid"] == "judge-1"
    assert stored["lines"][0]["amountText"] == "610rb"


def test_rejects_files_that_are_not_photos(client):
    response = client.post(
        "/api/readings/ledger-page",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 415


def test_requires_a_signed_in_user(anonymous_client):
    response = anonymous_client.post(
        "/api/readings/ledger-page",
        files={"file": ("page.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 401


def test_reads_a_receipt_and_stores_the_result(client, fake_db, fake_gemini):
    fake_gemini.reading = ReceiptReading(
        legible=True,
        merchant="Agen Sembako Jaya",
        items=[ReceiptItem(name="Beras", quantity_text="2", amount_text="640.000", confidence=0.9)],
        total_text="640.000",
        handwritten=True,
    )

    response = client.post(
        "/api/readings/receipt",
        files={"file": ("nota.jpg", b"fake-image-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["receipt"]["totalRp"] == 640_000
    assert body["receipt"]["itemsSumRp"] == 640_000
    stored = fake_db.collections["receiptReadings"][body["readingId"]]
    assert stored["uid"] == "judge-1"
    assert stored["receipt"]["merchant"] == "Agen Sembako Jaya"


def test_receipts_must_be_photos_too(client):
    response = client.post(
        "/api/readings/receipt",
        files={"file": ("receipt.pdf", b"%PDF", "application/pdf")},
    )

    assert response.status_code == 415
