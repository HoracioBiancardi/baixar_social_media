from fastapi.testclient import TestClient
from baixar_social_media.main import app

client = TestClient(app)


def test_index_page():
    response = client.get("/")
    assert response.status_code == 200
