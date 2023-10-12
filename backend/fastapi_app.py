# command to run: uvicorn fastapi_app:app --reload
import re
from typing import List
from fastapi import FastAPI, HTTPException, UploadFile, Form
from llama_index import ServiceContext
from pydantic import BaseModel, Field

# from llama_index.callbacks import CallbackManager, TokenCountingHandler
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

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
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
        logging.debug(f"Token Count: {app.token_counter.total_llm_token_count}")


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
        case "txt":
            load_text_chat_engine()
            return AITextDocument(file_name, LLM_NAME, app.callback_manager)
        # case "html":
        #     load_text_chat_engine()
        #     return AIHtmlDocument(
        #         f"file://{str(cfd)}/data/{file_name}",
        #         LLM_NAME,
        #         app.callback_manager
        #     )
        case "sqlite" | "db":
            load_database_chat_engine()
            return AIDataBase().from_uri(f"sqlite:///data/{file_name}")


async def handle_upload_url(upload_url):
    logging.debug(f"ending: {re.split(r'[./]', upload_url)}")
    match re.split(r"[./]", upload_url):
        case ["sqlite:", _, _, dir, _, "sqlite" | "db"] if dir == "data":
            load_database_chat_engine()
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


class MultipleChoiceQuestion(BaseModel):
    """Data Model for a multiple choice question"""

    question: str = Field(
        ...,
        description="""An interesting and unique question related to the main
        subject of the article.
        """,
    )
    correct_answer: str = Field(..., description="Correct answer to question")
    wrong_answer_1: str = Field(
        ..., description="a unique wrong answer to the question"
    )
    wrong_answer_2: str = Field(
        ...,
        description="""a unique wrong answer to the question which is different 
        from wrong_answer_1 and not an empty string
        """,
    )


class MultipleChoiceTest(BaseModel):
    """Data Model for a multiple choice test"""

    questions: List[MultipleChoiceQuestion]


class ErrorResponse(BaseModel):
    detail: str


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
            document = await handle_uploadfile(upload_file)
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
        {e.args}.
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


@app.get(
    "/quiz",
    # response_model=MultipleChoiceTest,
    responses={
        200: {"model": MultipleChoiceTest},
        400: {"model": ErrorResponse},
    },
)
def get_quiz():
    from llama_index.output_parsers import LangchainOutputParser
    from langchain.output_parsers import PydanticOutputParser
    from llama_index.prompts.default_prompts import (
        DEFAULT_TEXT_QA_PROMPT_TMPL,
        DEFAULT_REFINE_PROMPT_TMPL,
    )
    from llama_index.prompts import PromptTemplate
    from llama_index.response import Response

    vector_index = app.chat_engine.vector_index

    if not vector_index.ref_doc_info:
        raise HTTPException(
            status_code=400,
            detail="No context provided, please provide a url or a text file!",
        )

    lc_output_parser = PydanticOutputParser(pydantic_object=MultipleChoiceTest)
    output_parser = LangchainOutputParser(lc_output_parser)

    # format each prompt with langchain output parser instructions
    fmt_qa_tmpl = output_parser.format(DEFAULT_TEXT_QA_PROMPT_TMPL)
    fmt_refine_tmpl = output_parser.format(DEFAULT_REFINE_PROMPT_TMPL)
    qa_prompt = PromptTemplate(fmt_qa_tmpl, output_parser=output_parser)
    refine_prompt = PromptTemplate(fmt_refine_tmpl, output_parser=output_parser)

    question_query_engine = vector_index.as_query_engine(
        service_context=ServiceContext.from_defaults(),
        text_qa_template=qa_prompt,
        refine_template=refine_prompt,
    )

    response: Response = question_query_engine.query(
        """Please create a MultipleChoiceTest of 3 interesting and unique 
        MultipleChoiceQuestion about the main subject of the given context.
        """
    )

    return output_parser.parse(response.response)
    # return response.response_txt


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
