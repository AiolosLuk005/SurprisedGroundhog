def test_home_redirect(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/full/" in response.headers["Location"]

def test_health_check(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json == {"ok": True}
