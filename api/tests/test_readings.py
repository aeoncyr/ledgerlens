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
