# command to run: uvicorn fastapi_app:app --reload
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel

#from llama_index.callbacks import CallbackManager, TokenCountingHandler
    
import logging
import sys
from dotenv import load_dotenv
import pathlib
import os
import certifi
#import tiktoken

# Set-up Chat Engine: CondenseQuestionChatEngine with RetrieverQueryEngine
from script import (
    AITextDocument, 
    CustomLlamaIndexChatEngineWrapper, 
    set_up_chatbot,
)

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()

load_dotenv()
openai_log = "debug"

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

chat_bot, callback_manager, token_counter = set_up_chatbot()

app = FastAPI()

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


@app.post("/upload", response_model=TextSummaryModel)
async def upload_file(file: UploadFile | None = None):
    if not file:
        return TextSummaryModel(
            file_name="",
            text_category="",
            summary="No file was uploaded.",
            used_tokens=0,
        )
    
    # Ensure that the shared data folder exists
    os.makedirs("data", exist_ok=True)
    
    token_counter.reset_counts()
    cfd = pathlib.Path(__file__).parent
    try:     
        with open(cfd / "data" / file.filename, "wb") as f:
            f.write(file.file.read())
        
        document = AITextDocument(file.filename, "gpt-3.5-turbo", callback_manager)
        chat_bot.add_document(document)

    except Exception as e:
        return TextSummaryModel(
            file_name=file.filename,
            text_category="",
            summary=f"There was an error on uploading the file: {e.args}",
            used_tokens=int(token_counter.total_llm_token_count),
        )
    finally:
        file.file.close() # do I need this (with statement)?
        
    #logging.debug(document.text_summary)
    return TextSummaryModel(
        file_name=file.filename,
        text_category=document.text_category,
        summary=document.text_summary,
        used_tokens=token_counter.total_llm_token_count,
    )

@app.post("/qa_text", response_model=QAResponseModel)
async def qa_text(question: QuestionModel):
    token_counter.reset_counts()
    #logging.debug(question.prompt)
    chat_bot.update_temp(question.temperature)
    response = chat_bot.chat_engine.chat(
        question.prompt,
    )
    #logging.debug(response.response)

    return QAResponseModel(
        user_question= question.prompt,
        ai_answer= str(response),
        used_tokens=token_counter.total_llm_token_count,
    )

@app.get("/clear_storage", response_model=TextResponseModel)
async def clear_storage():
    try:
        chat_bot.empty_vector_store()
    except Exception as e:
        return TextResponseModel(message=f"Error: {e.args}")
    return TextResponseModel(message="Knowledge base succesfully cleared")

@app.get("/clear_history", response_model=TextResponseModel)
async def clear_history():
    try:
        chat_bot.clear_chat_history()
    except Exception as e:
        return TextResponseModel(message=f"Error: {e.args}")
    return TextResponseModel(message="Chat history succesfully cleared")

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