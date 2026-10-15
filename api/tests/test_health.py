def test_health_reports_version_and_model(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["model"] == "gemini-3.8-flash"
    assert "version" in body
