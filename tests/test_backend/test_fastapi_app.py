from fastapi import UploadFile
from backend.fastapi_app import app

from fastapi.testclient import TestClient

from pathlib import Path

client = TestClient(app)
cfd = Path(__file__).parent


def test_upload_text_file():
    # upload_file: UploadFile | None = None  # How to create manually???
    file_name = "example.txt"
    upload_file: UploadFile = Path(cfd / "data", file_name).open("rb")
    response = client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (file_name, upload_file)},
    )
    assert response.status_code == 200


def test_upload_url_webpage():
    url = "https://de.wikipedia.org/wiki/Don’t_repeat_yourself"
    response = client.post(
        "/upload", data={"upload_url": url}, files={"upload_file": ("", None)}
    )
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == url
    assert data.get("text_category", None) is not None
    assert data.get("summary", None) is not None
    assert data.get("used_tokens", None) is not None


def test_upload_url_database():
    url = "sqlite:///data/database.sqlite"
    response = client.post(
        "/upload", data={"upload_url": url}, files={"upload_file": ("", None)}
    )
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == url
    assert data.get("text_category", None) is not None
    assert data.get("summary", None) is not None
    assert data.get("used_tokens", None) is not None


def test_upload_url_and_file():
    upload_file: UploadFile | None = None
    file_name = "example.txt"
    upload_file: UploadFile = Path(cfd / "data", file_name).open("rb")
    response = client.post(
        "/upload",
        data={"upload_url": "https://de.wikipedia.org/wiki/Don’t_repeat_yourself"},
        files={"upload_file": (file_name, upload_file)},
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "You must provide either a file or URL to upload."
    }


def test_upload_no_url_and_no_file():
    response = client.post(
        "/upload", data={"upload_url": ""}, files={"upload_file": ("", None)}
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": "You must provide either a file or URL to upload."
    }


def test_upload_bad_url():
    url = "this/is/no/url"
    response = client.post(
        "/upload", data={"upload_url": url}, files={"upload_file": ("", None)}
    )
    assert response.status_code == 400
    assert response.json() == {
        "detail": f"There was a problem with the provided url: {url}"
    }


# def test_upload_database():
# """currently no small ( <200MB) database availabe"""
#     response = client.post("/upload")
#     assert response.status_code == 200


def test_ask_question_about_given_text():
    """Caution: test takes some time since openai API call required"""

    response = client.post(
        "/qa_text",
        json={
            "prompt": "Please give a summary of the given context.",
            "temperature": 0.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("ai_answer", None) is not None
    assert data.get("user_question", None) is not None
    assert data.get("used_tokens", None) is not None


def test_ask_question_about_given_database():
    """Caution: test takes some time since openai API call required"""

    response = client.post(
        "/qa_text",
        json={
            "prompt": "How much entries does the database have?",
            "temperature": 0.0,
        },
    )
    assert response.status_code == 200
    assert response.json()


def test_qa_with_empty_question():
    response = client.post(
        "/qa_text",
        json={
            "prompt": "",
            "temperature": 0.0,
        },
    )
    assert response.status_code == 200
    assert response.json().get("ai_answer") == "Empty question provided."


def test_qa_no_question_provided():
    response = client.post(
        "/qa_text",
        json={
            "temperature": 0.0,
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "No question provided."}


def test_qa_no_temperature_provided():
    response = client.post(
        "/qa_text",
        json={
            "prompt": "Please give a summary of the given context.",
        },
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "No temperature provided."}


def test_clear_storage():
    response = client.get("/clear_storage")
    assert response.status_code == 200
    assert response.json() == {"message": "Knowledge base succesfully cleared"}


def test_clear_history_route_up():
    response = client.get("/clear_history")
    assert response.status_code == 200
    assert response.json() == {"message": "Chat history succesfully cleared"}


# def test_quiz():
#     response = client.get("/quizz")
#     assert response.status_code == 200
