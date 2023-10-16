# python -m tests.test_backend.test_fastapi_app.py
import logging
import pytest

from pathlib import Path
import shutil
import sys

from fastapi import UploadFile
from fastapi.testclient import TestClient

from backend.fastapi_app import (
    app,
    clear_storage,
    DoubleUploadException,
    NoUploadException,
)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

client = TestClient(app)
cfd = Path(__file__).parent
example_file_dir = Path(__file__).parents[1] / "example_upload_files"


# Todo: put fixtures into conftest.py
@pytest.fixture
def text_file():
    file_name = "example.txt"
    upload_file: UploadFile = Path(example_file_dir, file_name).open("rb")
    yield upload_file
    # clean-up app storage after tests
    clear_storage()


@pytest.fixture
def url():
    return "https://de.wikipedia.org/wiki/Don’t_repeat_yourself"


@pytest.fixture
def url_db():
    file_name = "database.sqlite"
    app_data_dir = "data"
    destination_file = Path(cfd / app_data_dir / file_name)
    destination_file.parent.mkdir(exist_ok=True, parents=True)

    url_db_copied_to_app = f"sqlite:///{app_data_dir}/{file_name}"
    # destination = Path(__file__).parents[2] / "backend" / app_data_dir
    # destination = cfd / app_data_dir
    shutil.copy(example_file_dir / file_name, destination_file)

    yield url_db_copied_to_app
    # clear-up
    clear_storage()  # funktioniert noch nicht


@pytest.mark.ai_call
@pytest.mark.ai_embeddings
def test_upload_text_file(text_file):
    response = client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (text_file.filename, text_file)},
    )
    assert response.status_code == 200


@pytest.mark.ai_call
@pytest.mark.ai_embeddings
def test_upload_url_webpage(url):
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


# def test_test_route():
#     #data = {"upload_url": "sqlite:///data/database.sqlite"}
#     file_name = "example.txt"
#     file = Path(example_file_dir, file_name).open("rb")
#     response = client.post(
#         "/upload",
#         files={"upload_file": ("example.txt", file)}
#     )

#     assert response.status_code == 200
#     assert response.json().get("detail") == "example"


def test_upload_url_database(url_db):
    data = {"upload_url": "sqlite:///data/database.sqlite"}
    # working:
    # file_name = "example.txt"
    # file = Path(example_file_dir, file_name).open("rb")
    # response = client.post(
    #     "/upload", data=data, files={"upload_file": (file_name, file)}
    # )

    response = client.post("/upload", data=data, files=None)
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == url_db
    assert data.get("text_category", None) is not None
    assert data.get("summary", None) is not None
    assert data.get("used_tokens", None) is not None


def test_upload_url_and_file(url, text_file):
    with pytest.raises(DoubleUploadException):
        response = client.post(
            "/upload",
            data={"upload_url": url},
            files={"upload_file": (text_file.filename, text_file)},
        )
        assert response.status_code == 400
        assert response.json() == {
            "detail": "You must provide either a file or URL to upload."
        }


def test_upload_no_url_and_no_file():
    with pytest.raises(NoUploadException):
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


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
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


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
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


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
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

if __name__ == "__main__":
    file_name = "example.txt"
    print(str(cfd))
