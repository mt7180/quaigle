from backend.fastapi_app import app

from fastapi.testclient import TestClient

client = TestClient(app)


def test_upload_file():
    response = client.get("/upload")
    assert response.status_code == 200
