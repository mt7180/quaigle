# command to run: uvicorn fastapi_app:app --reload
from typing import List
from fastapi import FastAPI, HTTPException, UploadFile
from llama_index import ServiceContext
from pydantic import BaseModel, Field

# from llama_index.callbacks import CallbackManager, TokenCountingHandler

import logging
import sys
from dotenv import load_dotenv
import pathlib
import os
import certifi

# import tiktoken

# Set-up Chat Engine: CondenseQuestionChatEngine with RetrieverQueryEngine
from script import (
    AITextDocument,
    AIHtmlDocument,
    # CustomLlamaIndexChatEngineWrapper,
    set_up_chatbot,
)

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()
LLM_STR = "gpt-3.5-turbo"

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


class UploadModel(BaseModel):
    file: UploadFile | str


class QAResponseModel(BaseModel):
    user_question: str
    ai_answer: str
    used_tokens: int


class TextResponseModel(BaseModel):
    message: str


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


@app.post("/upload", response_model=TextSummaryModel)
async def upload_file(upload: UploadModel):
    if not upload:
        return TextSummaryModel(
            file_name="",
            text_category="",
            summary="No file/url was uploaded.",
            used_tokens=0,
        )

    token_counter.reset_counts()
    cfd = pathlib.Path(__file__).parent
    try:
        if isinstance(upload.file, str):
            document = AIHtmlDocument(upload.file, LLM_STR, callback_manager)
            file_name = upload.file
        else:
            # Ensure that the data folder exists
            os.makedirs("data", exist_ok=True)
            with open(cfd / "data" / upload.file.filename, "wb") as f:
                f.write(upload.file.read())
            document = AITextDocument(upload.file.filename, LLM_STR, callback_manager)
            file_name = upload.file.filename
        chat_bot.add_document(document)

    except Exception as e:
        return TextSummaryModel(
            file_name=file_name,
            text_category="",
            summary=f"There was an error on uploading the file: {e.args}",
            used_tokens=int(token_counter.total_llm_token_count),
        )
    finally:
        if not isinstance(upload.file, str):
            upload.file.close()  # do I need this (with statement)?

    # logging.debug(document.text_summary)
    return TextSummaryModel(
        file_name=file_name,
        text_category=document.text_category,
        summary=document.text_summary,
        used_tokens=token_counter.total_llm_token_count,
    )


@app.post("/qa_text", response_model=QAResponseModel)
async def qa_text(question: QuestionModel):
    token_counter.reset_counts()
    # logging.debug(question.prompt)
    chat_bot.update_temp(question.temperature)
    response = chat_bot.chat_engine.chat(
        question.prompt,
    )
    # logging.debug(response.response)

    return QAResponseModel(
        user_question=question.prompt,
        ai_answer=str(response),
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


@app.get("/quizz")
def get_quizz():
    from llama_index.output_parsers import LangchainOutputParser

    # https://gpt-index.readthedocs.io/en/stable/examples/query_engine/pydantic_query_engine.html
    # https://gpt-index.readthedocs.io/en/stable/examples/output_parsing/guidance_pydantic_program.html

    from langchain.output_parsers import PydanticOutputParser
    from llama_index.prompts.default_prompts import (
        DEFAULT_TEXT_QA_PROMPT_TMPL,
        DEFAULT_REFINE_PROMPT_TMPL,
    )
    from llama_index.prompts import PromptTemplate

    vector_index = chat_bot.vector_index

    if not vector_index.ref_doc_info:
        raise HTTPException(detail="No context provided")

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

    response = question_query_engine.query(
        """Please create a MultipleChoiceTest of 3 interesting and unique 
        MultipleChoiceQuestion about the main subject of the given context.
        """
    )

    # # Construct sub-question query engine
    # query_engine_tools = [
    #     QueryEngineTool(
    #         query_engine=info_query_engine,
    #         metadata=ToolMetadata(
    #             name="article_info",
    #             description="""Provides information about the specific subject
    #               of the article
    #             """,
    #         ),
    #     ),
    #     QueryEngineTool(
    #         query_engine=question_query_engine,
    #         metadata=ToolMetadata(
    #             name="Multiple_Choice_Question",
    #             description="""Provides a multiple choice question about a given
    #             subject  of the article""",
    #         ),
    #     ),
    # ]

    # s_engine = SubQuestionQueryEngine.from_defaults(
    #     #question_gen=question_gen,
    #     query_engine_tools=query_engine_tools,
    #     #response_synthesizer = get_response_synthesizer(
    #           response_mode=ResponseMode.COMPACT
    #     )
    # )

    # # # # Query the sub-questions
    # response =  s_engine.query(
    #     """Please create 2 interesting and unique MultipleCoiceQuestions about the
    #      main subject of the given context.
    #     """
    # )
    # Problem: subqueryengine has no output parser ...

    print(str(response))
    return response


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
