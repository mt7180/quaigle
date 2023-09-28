# command to run: uvicorn fastapi_app:app --reload
from tempfile import NamedTemporaryFile
from typing import BinaryIO
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel, Field
from marvin import ai_fn, AIApplication, ai_model
from marvin import settings as marvin_settings
import marvin.tools.filesystem
import marvin.tools.shell
from marvin.tools.chroma import MultiQueryChroma as marvin_QueryChroma

from llama_index.callbacks import CallbackManager, TokenCountingHandler
    
import logging
import sys
from dotenv import load_dotenv
import pathlib
import os
import certifi
import tiktoken

# Set-up Chat Engine: CondenseQuestionChatEngine with RetrieverQueryEngine
from script import AITextDocument, CustomLlamaIndexChatEngineWrapper, set_up_chatbot 

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

load_dotenv()

chat_engine, callback_manager, token_counter = set_up_chatbot()

app = FastAPI()

class TextSummary(BaseModel):
    file_name: str
    text_category: str
    summary: str
    used_tokens: int


class QAResponse(BaseModel):
    ai_answer: dict[str,str] = Field(
        default_factory=dict, 
        description="A mapping containing the user question to the ai answer."
    )
    used_tokens: int


# @app.on_event("startup")
# def on_startup():

@app.post("/upload", response_model=TextSummary)
async def upload_file(file: UploadFile | None = None):
    if not file:
        return  #{"message": "No upload file sent"}
    
    # Ensure that the shared data folder exists
    os.makedirs("data", exist_ok=True)
    
    token_counter.reset_counts() # TODO: put into qa route

    try:     
        with open(f"data/{file.filename}", "wb") as f:
            f.write(file.file.read())
        
        document = AITextDocument(file.filename, "gpt-3.5-turbo", callback_manager)
        chat_engine.add_document(document)

        # data_file_dir = pathlib.Path.cwd() / "data"
    except Exception as e:
        return TextSummary(
            file_name=file.filename,
            text_category="",
            summary=f"There was an error on uploading the file: {e}",
            used_tokens=int(token_counter.total_llm_token_count),
        )
    finally:
        file.file.close() # do I need this (with statement)?
        
    logging.debug(document.text_summary)
    return TextSummary(
        file_name=file.filename,
        text_category = document.text_category,
        summary= document.text_summary,
        used_tokens=token_counter.total_llm_token_count,
    )

