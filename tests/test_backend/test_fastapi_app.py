# python -m tests.test_backend.test_fastapi_app.py
import logging
import os
import io
import pytest
from pathlib import Path
import sys

from fastapi.testclient import TestClient

from backend.fastapi_app import app
from backend.models import (
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
            if app.state.chat_engine:
                app.state.chat_engine.clear_data_storage()
                logging.debug("chat engine cleared...")
                app.state.chat_engine = None
            if (file := Path(backend_dir / "data" / file_name)).is_file():
                os.remove(file)


@pytest.fixture
def url():
    yield "https://de.wikipedia.org/wiki/Don’t_repeat_yourself"
    # clean-up (clear_storage)
    if app.state.chat_engine:
        app.state.chat_engine.clear_data_storage()
        logging.debug("chat engine cleared...")
    app.state.chat_engine = None
    app.state.callback_manager = None
    app.state.token_counter = None


@pytest.fixture
def db_file():
    file_name = "database.sqlite"
    with Path(example_file_dir, file_name).open("rb") as upload_file:
        try:
            yield upload_file
        finally:
            if app.state.chat_engine:
                app.state.chat_engine.clear_data_storage()
                logging.debug("chat engine cleared...")
                app.state.chat_engine = None
            if (file := Path(backend_dir / "data" / file_name)).is_file():
                os.remove(file)


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


def test_upload_database_file(db_file):
    db_file_name = Path(db_file.name).name
    response = client.post(
        "/upload",
        data={"upload_url": ""},
        files={"upload_file": (db_file_name, db_file)},
    )

    assert app.state.chat_engine is not None
    assert app.state.chat_engine.data_category == "database"
    assert app.state.callback_manager is None  # is None in database mode
    assert app.state.token_counter is not None

    assert response.status_code == 200
    data = response.json()
    # test if keys in response and if not None
    assert data.get("file_name", None) == db_file_name
    assert data.get("text_category") == "database"
    assert data.get("summary", None) is not None
    assert len(data.get("summary")) > 13
    assert data.get("used_tokens", None) is not None


def test_upload_url_and_file(url: str, text_file: io.BytesIO) -> None:
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
        "detail": f"""There was a problem with the provided url (MissingSchema):
            {url}
            """
    }


@pytest.mark.ai_call
@pytest.mark.ai_gpt35
def test_ask_question_about_given_text(text_file):
    """Caution: openai API call required"""
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
def test_ask_question_about_given_database(db_file):
    """Caution: openai API call required"""
    # data = {"upload_url": url_db}
    upload_response = client.post(
        "/upload", files={"upload_file": (Path(db_file.name).name, db_file)}
    )
    assert upload_response.status_code == 200

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
