# python -m tests.test_backend.test_fastapi_app.py
import logging
import os
import pytest

from pathlib import Path
import shutil
import sys

from fastapi.testclient import TestClient

from backend.fastapi_app import (
    app,
    EmptyQuestionException,
    DoubleUploadException,
    NoUploadException,
)

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

client = TestClient(app)
cfd = Path(__file__).parent
backend_dir = Path(__file__).parents[2] / "backend"
example_file_dir = Path(__file__).parents[1] / "example_upload_files"


# Todo: put fixtures into conftest.py
@pytest.fixture
def text_file():
    file_name = "example.txt"
    with Path(example_file_dir, file_name).open("rb") as upload_file:
        try:
            yield upload_file
        # clean-up app storage after tests
        finally:
            if app.chat_engine:
                app.chat_engine.clear_data_storage()
                logging.debug("chat engine cleared...")
                app.chat_engine = None
            if file := Path(backend_dir / "data" / file_name).is_file():
                os.remove(file)


@pytest.fixture
def url():
    yield "https://de.wikipedia.org/wiki/Don’t_repeat_yourself"
    # clean-up (clear_storage)
    if app.chat_engine:
        app.chat_engine.clear_data_storage()
        logging.debug("chat engine cleared...")
    app.chat_engine = None
    app.callback_manager = None
    app.token_counter = None


@pytest.fixture
def url_db():
    file_name = "database.sqlite"
    app_data_dir = "data"
    destination_file = Path(backend_dir / app_data_dir / file_name)
    destination_file.parent.mkdir(exist_ok=True, parents=True)

    url_db_copied_to_app = f"sqlite:///{app_data_dir}/{file_name}"
    shutil.copy(example_file_dir / file_name, destination_file)
    yield url_db_copied_to_app
    # clean-up (clear_storage)
    if app.chat_engine:
        app.chat_engine.clear_data_storage()
        logging.debug("chat engine cleared...")
    app.chat_engine = None
    app.token_counter = None
    if destination_file.is_file():
        os.remove(destination_file)


@pytest.mark.ai_call
@pytest.mark.ai_embeddings
def test_upload_text_file(text_file):
    response = client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (text_file.name, text_file)},
    )
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == text_file.name
    assert data.get("text_category", None) is not None
    assert data.get("summary", None) is not None
    assert data.get("used_tokens", None) is not None


@pytest.mark.ai_call
@pytest.mark.ai_embeddings
def test_upload_url_webpage(url):
    response = client.post("/upload", data={"upload_url": url}, files=None)
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
    data = {"upload_url": url_db}
    response = client.post("/upload", data=data, files=None)

    assert app.chat_engine is not None
    assert app.chat_engine.data_category == "database"
    # assert app.callback_manager is not None # is None in database mode
    assert app.token_counter is not None

    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == url_db
    # assert data.get("text_category", None) is not None
    assert data.get("text_category") == "database"
    assert data.get("summary", None) is not None
    assert len(data.get("summary")) > 13
    assert data.get("used_tokens", None) is not None


def test_upload_url_and_file(url: str, text_file):
    with pytest.raises(DoubleUploadException):
        client.post(
            "/upload",
            data={"upload_url": url},
            files={"upload_file": (text_file.name, text_file)},
        )


def test_upload_no_url_and_no_file():
    with pytest.raises(NoUploadException):
        client.post("/upload", data={"upload_url": ""}, files=None)
    # assert response.status_code == 400


def test_upload_bad_url():
    url = "this/is/no/url"
    response = client.post("/upload", data={"upload_url": url}, files=None)
    assert response.status_code == 400
    assert response.json() == {
        "detail": f"There was a problem with the provided url (MissingSchema): {url}"
    }


# def test_upload_database():
# """currently no small ( <200MB) database availabe"""
#     response = client.post("/upload")
#     assert response.status_code == 200


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
def test_ask_question_about_given_text(text_file):
    """Caution: test takes some time since openai API call required"""
    client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (text_file.name, text_file)},
    )
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
def test_ask_question_about_given_database(url_db):
    """Caution: test takes some time since openai API call required"""
    data = {"upload_url": url_db}
    res1 = client.post("/upload", data=data, files=None)
    assert res1.status_code == 200

    response = client.post(
        "/qa_text",
        json={
            # "prompt": "How much entries does the database have?",
            "prompt": """Which name has the user who wrote the largest amount 
            of helpful reviews?
            """,
            "temperature": 0.0,
        },
    )
    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("ai_answer", None) is not None
    assert "Sorry, no context loaded." not in data.get("ai_answer")
    assert data.get("user_question", None) is not None
    assert data.get("used_tokens", None) is not None


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
def test_qa_with_empty_question(text_file):
    client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (text_file.name, text_file)},
    )
    with pytest.raises(EmptyQuestionException):
        client.post(
            "/qa_text",
            json={
                "prompt": "",
                "temperature": 0.0,
            },
        )


def test_clear_storage():
    response = client.get("/clear_storage")
    assert response.status_code == 200
    assert response.json() == {"message": "Knowledge base succesfully cleared"}


def test_clear_history_no_context_loaded():
    response = client.get("/clear_history")
    assert response.status_code == 200
    assert response.json() == {
        "message": "No active chat available, please load a document."
    }


# def test_quiz():
#     response = client.get("/quizz")
#     assert response.status_code == 200

if __name__ == "__main__":
    file_name = "example.txt"
    print(str(cfd))
