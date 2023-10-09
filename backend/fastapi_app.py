# command to run: uvicorn fastapi_app:app --reload
import re
from fastapi import FastAPI, Form, HTTPException, UploadFile
from pydantic import BaseModel
from requests.exceptions import MissingSchema

import logging
import sys
from dotenv import load_dotenv
import pathlib
import os
import certifi

from script import (
    CustomLlamaIndexChatEngineWrapper,
    AITextDocument,
    AIHtmlDocument,
    set_up_text_chatbot,
)

from script_database import (
    AIDataBase,
    DataChatBotWrapper,
    set_up_database_chatbot,
)

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
LLM_NAME = "gpt-3.5-turbo"

load_dotenv()
openai_log = "debug"

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

# Set-up Chat Engine: CondenseQuestionChatEngine with RetrieverQueryEngine


app = FastAPI()
cfd = pathlib.Path(__file__).parent


app.chat_engine: CustomLlamaIndexChatEngineWrapper | DataChatBotWrapper | None = None
app.callback_manager = None
app.token_counter = None


class TextSummaryModel(BaseModel):
    file_name: str
    text_category: str
    summary: str
    used_tokens: int


class QuestionModel(BaseModel):
    prompt: str
    temperature: float


class QAResponseModel(BaseModel):
    user_question: str
    ai_answer: str
    used_tokens: int


class TextResponseModel(BaseModel):
    message: str


def load_text_chat_engine():
    logging.debug(f"is there a chat engine?: {app.chat_engine is not None}")
    if not app.chat_engine or app.chat_engine.data_category == "database":
        logging.debug("setting up text chatbot")
        app.chat_engine, app.callback_manager, app.token_counter = set_up_text_chatbot()
        print(app.token_counter.total_llm_token_count)
        if app.callback_manager:
            print("callback manager not Null")
    # elif chat_engine.data_category == "database":
    #     if chat_engine.data_category


def load_database_chat_engine():
    if not app.chat_engine or app.chat_engine.data_category != "database":
        logging.debug("setting up database chatbot")
        (
            app.chat_engine,
            app.callback_manager,
            app.token_counter,
        ) = set_up_database_chatbot()
        logging.debug(f"Token counter there?: {app.token_counter is not None}")


async def handle_uploadfile(
    upload_file: UploadFile,
) -> AITextDocument | AIDataBase | None:
    file_name = upload_file.filename
    with open(cfd / "data" / file_name, "wb") as f:
        f.write(await upload_file.read())

    logging.debug(upload_file.filename.split(".")[-1])
    match upload_file.filename.split(".")[-1]:
        case ["txt"]:
            load_text_chat_engine()
            return AITextDocument(file_name, LLM_NAME, app.callback_manager)
        case ["sqlite" | "db"]:
            load_database_chat_engine()
            return AIDataBase().from_uri(f"sqlite:///data/{file_name}")


async def handle_upload_url(upload_url):
    logging.debug(f"ending: {re.split(r'[./]', upload_url)}")
    match re.split(r"[./]", upload_url):
        case ["sqlite:", _, _, dir, _, "sqlite" | "db"] if dir == "data":
            load_database_chat_engine()
            print(app.token_counter.total_llm_token_count, upload_url, cfd)
            document: AIDataBase = AIDataBase.from_uri(upload_url)
            return document
        case [*_, dir, file_name, "txt"] if dir == "data":
            try:
                load_text_chat_engine()
                return AITextDocument(file_name, LLM_NAME, app.callback_manager)
            except OSError:
                raise FileNotFoundError
        case [http, *_] if "http" in http.lower():
            load_text_chat_engine()
            return AIHtmlDocument(upload_url, LLM_NAME, app.callback_manager)
        case _:
            raise FileNotFoundError


@app.post("/upload", response_model=TextSummaryModel)
async def upload_file(
    upload_file: UploadFile | None = None, upload_url: str = Form("")
):
    # TOKEN_COUNTER.reset_counts()
    message = ""
    text_category = ""
    file_name = ""
    try:
        if upload_file:
            if upload_url:
                raise HTTPException(
                    status_code=400, detail="You can not provide both, file and URL."
                )
            os.makedirs("data", exist_ok=True)
            document = handle_uploadfile(upload_file)
            file_name = upload_file.filename
        elif upload_url:
            document = await handle_upload_url(upload_url)
            file_name = upload_url
        else:
            raise HTTPException(
                status_code=400,
                detail="You must provide either a file or URL to upload.",
            )
        app.chat_engine.add_document(document)
        message = document.summary
        text_category = document.category
    except HTTPException as e:
        message = (f"There was an error on uploading your text/ url: {e.args}",)
    except MissingSchema as e:
        message = f"There was a problem with the provided url: {e.args}"
    except OSError as e:
        message = f"""There was an unexpected OSError on saving the file: 
        {e.args}, please ask the admin for write permissions
        """
    return TextSummaryModel(
        file_name=file_name,
        text_category=text_category,
        summary=message,
        used_tokens=app.token_counter.total_llm_token_count,
    )


@app.post("/qa_text", response_model=QAResponseModel)
async def qa_text(question: QuestionModel):
    app.token_counter.reset_counts()
    # logging.debug(question.prompt)
    app.chat_engine.update_temp(question.temperature)
    response = app.chat_engine.answer_question(question)
    # logging.debug(response.response)

    return QAResponseModel(
        user_question=question.prompt,
        ai_answer=str(response),
        used_tokens=app.token_counter.total_llm_token_count,
    )


@app.get("/clear_storage", response_model=TextResponseModel)
async def clear_storage():
    app.chat_engine.clear_data_storage()
    # logging.DEBUG("vector store cleared...")
    return TextResponseModel(message="Knowledge base succesfully cleared")


@app.get("/clear_history", response_model=TextResponseModel)
async def clear_history():
    message = app.chat_engine.clear_chat_history()
    # logging.DEBUG("chat history cleared...")
    return TextResponseModel(message=message)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        use_colors=True,
        reload=True,
    )
