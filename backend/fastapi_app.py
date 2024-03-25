# command to run: uvicorn backend.fastapi_app:app --reload
import os
import re
import logging
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, Form
from llama_index import ServiceContext
from requests.exceptions import MissingSchema
from dotenv import load_dotenv
import errno
import certifi

import sentry_sdk

from .script_RAG import (
    AITextDocument,
    AIPdfDocument,
    AIHtmlDocument,
    set_up_text_chatbot,
)
from .script_SQL_querying import (
    AIDataBase,
    set_up_database_chatbot,
)
from .models import (
    DoubleUploadException,
    NoUploadException,
    EmptyQuestionException,
    TextSummaryModel,
    QuestionModel,
    QAResponseModel,
    TextResponseModel,
    MultipleChoiceTest,
    ErrorResponse,
)
from .helpers import load_aws_secrets

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
LLM_NAME = "gpt-3.5-turbo"

load_dotenv()  # can be set to override=True, if values changed
DEBUG_MODE = int(os.getenv("DEBUG_MY_APP", 0))

if DEBUG_MODE:
    openai_log = "debug"
    logging_level = logging.DEBUG
    app_dir = "backend"
else:
    logging_level = logging.INFO
    load_aws_secrets()
    SENTRY_DSN = os.getenv("SENTRY_DSN_BACKEND")
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # Enable performance monitoring
        enable_tracing=True,
    )
    app_dir = "code"

logging.basicConfig(stream=sys.stdout, level=logging_level)
logging.getLogger(__name__).addHandler(logging.StreamHandler(stream=sys.stdout))

logging.info(f"Debug enabled: {bool(DEBUG_MODE)}")

app = FastAPI()
cfd = Path(__file__).parent
data_dir = "data"
logging.info(f"Current fastapiapp dir : {cfd}")

# Set-up Chat Engine:
# - LlamaIndex CondenseQuestionChatEngine with RetrieverQueryEngine for text files
# - or querying a database with langchain SQLDatabaseChain and Runnables
app.state.chat_engine = None
app.state.callback_manager = None
app.state.token_counter = None


def load_text_chat_engine() -> None:
    if not app.state.chat_engine or app.state.chat_engine.data_category == "database":
        logging.debug("setting up text chatbot")
        logging.debug(f"Debug: {DEBUG_MODE}")
        (
            app.state.chat_engine,
            app.state.callback_manager,
            app.state.token_counter,
        ) = set_up_text_chatbot()


def load_database_chat_engine() -> None:
    if not app.state.chat_engine or app.state.chat_engine.data_category != "database":
        logging.debug("setting up database chatbot")
        (
            app.state.chat_engine,
            app.state.callback_manager,  # is None in database mode
            app.state.token_counter,
        ) = set_up_database_chatbot()


async def handle_uploadfile(
    upload_file: UploadFile,
) -> AITextDocument | AIDataBase | AIPdfDocument | None:
    if not (file_name := upload_file.filename):
        return None
    with open(cfd / data_dir / file_name, "wb") as f:
        f.write(await upload_file.read())
    match upload_file.filename.split(".")[-1]:
        case "txt":
            load_text_chat_engine()
            return AITextDocument(file_name, LLM_NAME, app.state.callback_manager)
        case "pdf":
            load_text_chat_engine()
            return AIPdfDocument(file_name, LLM_NAME, app.state.callback_manager)
        case "sqlite" | "db":
            uri = f"sqlite:///{app_dir}/{data_dir}/{file_name}"
            logging.debug(f"uri: {uri} debug {DEBUG_MODE}")
            load_database_chat_engine()
            return AIDataBase.from_uri(uri)
    return None


async def handle_upload_url(upload_url: str) -> AITextDocument | AIHtmlDocument:
    match re.split(r"[./]", upload_url):
        case [*_, dir, file_name, "txt"] if dir == "data":
            try:
                load_text_chat_engine()
                return AITextDocument(file_name, LLM_NAME, app.state.callback_manager)
            except OSError:
                raise FileNotFoundError(
                    errno.ENOENT,
                    os.strerror(errno.ENOENT) + " in data folder",
                    file_name,
                )
        case [http, *_] if "http" in http.lower():
            load_text_chat_engine()
            return AIHtmlDocument(upload_url, LLM_NAME, app.state.callback_manager)
        case _:
            raise MissingSchema


@app.post("/upload", response_model=TextSummaryModel)
async def upload_file(
    upload_file: UploadFile | None = None, upload_url: str = Form("")
) -> TextSummaryModel:
    message = ""
    text_category = ""
    file_name: str | None = ""
    used_tokens = 0
    try:
        if upload_file:
            if upload_url:
                raise DoubleUploadException("You can not provide both, file and URL.")
            if not (file_name := upload_file.filename):
                return TextSummaryModel(
                    file_name="",
                    text_category=text_category,
                    summary=message,
                    used_tokens=used_tokens,
                )
            destination_file = Path(cfd / "data" / file_name)
            destination_file.parent.mkdir(exist_ok=True, parents=True)
            document = await handle_uploadfile(upload_file)

        elif upload_url:
            document = await handle_upload_url(upload_url)
            file_name = upload_url
        else:
            raise NoUploadException(
                "You must provide either a file or URL to upload.",
            )
        if app.state.chat_engine and document:
            app.state.chat_engine.add_document(document)
            message = document.summary
            text_category = document.category
            used_tokens = app.state.token_counter.total_llm_token_count
    except MissingSchema:
        raise HTTPException(
            status_code=400,
            detail=f"""There was a problem with the provided url (MissingSchema):
            {upload_url}
            """,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        raise HTTPException(
            status_code=400,
            detail=f"There was an unexpected OSError on uploading the file:{e}",
        )
    logging.debug(f"engine_up?: {app.state.chat_engine is not None}")
    logging.debug(f"message: {message}")
    return TextSummaryModel(
        file_name=file_name,
        text_category=text_category,
        summary=message,
        used_tokens=used_tokens,
    )


@app.post("/qa_text", response_model=QAResponseModel)
async def qa_text(question: QuestionModel) -> QAResponseModel:
    logging.debug(f"engine_up?: {app.state.chat_engine is not None}")
    if not question.prompt:
        raise EmptyQuestionException(
            "Your Question is empty, please type a message and resend it."
        )
    if app.state.chat_engine:
        app.state.token_counter.reset_counts()
        app.state.chat_engine.update_temp(question.temperature)
        response = app.state.chat_engine.answer_question(question)
        ai_answer = str(response)
        used_tokens = app.state.token_counter.total_llm_token_count
    else:
        ai_answer = "Sorry, no context loaded. Please upload a file or url."
        used_tokens = 0

    return QAResponseModel(
        user_question=question.prompt,
        ai_answer=ai_answer,
        used_tokens=used_tokens,
    )


@app.get("/clear_storage", response_model=TextResponseModel)
async def clear_storage():
    if app.state.chat_engine:
        app.state.chat_engine.clear_data_storage()
        logging.info("chat engine cleared...")
    if (cfd / "data").exists():
        for file in Path(cfd / "data").iterdir():
            os.remove(file)
    app.state.chat_engine = None
    app.state.token_counter = None
    app.state.callback_manager = None
    return TextResponseModel(message="Knowledge base succesfully cleared")


@app.get("/clear_history", response_model=TextResponseModel)
async def clear_history():
    if app.state.chat_engine:
        message = app.state.chat_engine.clear_chat_history()
        # logging.debug("chat history cleared...")
        return TextResponseModel(message=message)
    return TextResponseModel(
        message="No active chat available, please load a document."
    )


@app.get(
    "/quiz",
    responses={
        200: {"model": MultipleChoiceTest},
        400: {"model": ErrorResponse},
    },
)
def get_quiz():
    if not app.state.chat_engine or not app.state.chat_engine.vector_index.ref_doc_info:
        raise HTTPException(
            status_code=400,
            detail="No context provided, please provide a url or a text file!",
        )

    if app.state.chat_engine.data_category == "database":
        raise HTTPException(
            status_code=400,
            detail="""A database is loaded, but no valid context for a quiz.
            Please provide a webpage url or a text file!
            """,
        )

    quiz = generate_quiz_from_context()
    return quiz


def generate_quiz_from_context():
    # Possible enhancements for future:
    # use  Llamaindex DatasetGenerator and RelevancyEvaluator in combination with gpt4
    # to generate a list of questions of relevance that could be asked about the data
    # https://gpt-index.readthedocs.io/en/latest/examples/evaluation/QuestionGeneration.html
    # https://betterprogramming.pub/llamaindex-how-to-evaluate-your-rag-retrieval-augmented-generation-applications-2c83490f489

    from llama_index.output_parsers import LangchainOutputParser
    from langchain.output_parsers import PydanticOutputParser
    from llama_index.prompts.default_prompts import (
        DEFAULT_TEXT_QA_PROMPT_TMPL,
        DEFAULT_REFINE_PROMPT_TMPL,
    )
    from llama_index.prompts import PromptTemplate
    from llama_index.response import Response

    vector_index = app.state.chat_engine.vector_index
    lc_output_parser = PydanticOutputParser(pydantic_object=MultipleChoiceTest)
    output_parser = LangchainOutputParser(lc_output_parser)

    # format each prompt with langchain output parser instructions
    fmt_qa_tmpl = output_parser.format(DEFAULT_TEXT_QA_PROMPT_TMPL)
    fmt_refine_tmpl = output_parser.format(DEFAULT_REFINE_PROMPT_TMPL)
    qa_prompt = PromptTemplate(fmt_qa_tmpl, output_parser=output_parser)
    refine_prompt = PromptTemplate(fmt_refine_tmpl, output_parser=output_parser)

    question_query_engine = vector_index.as_query_engine(
        service_context=ServiceContext.from_defaults(llm="gpt-3.5-turbo"),
        text_qa_template=qa_prompt,
        refine_template=refine_prompt,
    )

    response: Response = question_query_engine.query(
        """Please create a MultipleChoiceTest of 3 interesting and unique 
        MultipleChoiceQuestions about the main subject of the given context. Remember to
        only formulate questions about the given context.
        """
    )

    return output_parser.parse(response.response)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.fastapi_app:app",
        host="0.0.0.0",
        port=8000,
        workers=1,
        use_colors=True,
        reload=True,
    )
