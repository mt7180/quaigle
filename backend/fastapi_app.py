# command to run: uvicorn fastapi_app:app --reload
from tempfile import NamedTemporaryFile
from typing import BinaryIO
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel, Field
from marvin import ai_fn, AIApplication, ai_model
from marvin import settings as marvin_settings
import marvin.tools.filesystem
import marvin.tools.shell
import marvin.tools.chroma
import marvin.utilities.embeddings
from dotenv import load_dotenv
import pathlib
import os

import certifi

# workaround for mac to solve "SSL: CERTIFICATE_VERIFY_FAILED Error"
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()
os.environ["SSL_CERT_FILE"] = certifi.where()



load_dotenv()
marvin_settings.openai.api_key = os.getenv('OPENAI_API_KEY')

app = FastAPI()

class TextSummary(BaseModel):
    file_name: str
    summary: str


class QAResponse(BaseModel):
    ai_answer: dict[str,str] = Field(
        default_factory=dict, 
        description="A mapping containing the user question to the ai answer."
    )

marvin_settings.llm_temperature = 0
marvin_settings.log_level = "DEBUG"

@ai_fn(
    instructions="You are an accurate and experienced copywriter."
)
def summarize_from_string(text: str) -> str:
    """ Please write a unique and short summary of the given text 
    using friendly, easy to read language, but stay correct and focussed. 
    The summary should have at maximum 10 sentences.
    """
    # noqa: E501

FILE_DIR = pathlib.Path.cwd() / "data"

@ai_fn(
    instructions="You are an accurate and experienced copywriter.",
    tools=[
        marvin.tools.filesystem.ReadFile(root_dir=FILE_DIR),
        marvin.tools.shell.Shell(
            require_confirmation=True, working_directory=FILE_DIR
        ),
       
    ],
)
def summarize_from_file(file_name: str) -> str:
    f""" You are responsible for writing a summary of the text given in the text file {file_name},
    located at {FILE_DIR}. You are not allowed to write or modify any files. You are only allowed to read files from {FILE_DIR}. 
    Please write a unique and short summary of the content of the given text file
    using friendly, easy to read language, but stay correct and focussed.
    The summary should have at maximum 10 sentences and .
    """
    # noqa: E501


async def summarize_text(file_name: str) -> str:
    cwd = pathlib.Path.cwd()
    data_file_path = cwd / "data" / file_name
    print(str(data_file_path))
    with open(data_file_path,"r") as f:
        text = " ".join(f.read().split('\n'))
    return summarize_from_string(text)

@app.post("/upload", response_model=TextSummary)
async def upload_file(file: UploadFile | None = None):
    if not file:
        return  #{"message": "No upload file sent"}
    
    # Ensure that the shared data folder exists
    os.makedirs("data", exist_ok=True)

    try:     
        with open(f"data/{file.filename}", "wb") as f:
            f.write(file.file.read())
        # summary_str= await summarize_text(file.filename)
        # with NamedTemporaryFile(delete=False, mode="w", encoding="utf-8") as temp_file:
        # Save the uploaded file to a temporary location
        #     shutil.copyfileobj(file.file, temp_file)

        cwd = pathlib.Path.cwd()
        data_file_dir = cwd / "data"
    except Exception as e:
        return TextSummary(
            file_name=file.name, 
            summary=f"There was an error on uploading the file: {e}"
        )
    finally:
        file.file.close()
        
    summary_str = summarize_from_file(file.filename)
    print(summary_str)
    return TextSummary(
        file_name=file.filename,
        summary= summary_str
    )

class QAState(BaseModel):
    history: list[QAResponse] = Field(
        default_factory=list,
        description=(
            "A place to record the history of questions and answers concerning the content of one given file."
        ),
    )
    #tests_passing: bool = False

@app.get("/qa_text")
def run(question: str) -> str:
    description = ("A chatbot. Users will ask questions concerning a given text. ")

    qa = AIApplication(
        name="Chatbot",
        #state=QAState(),
        #history=
        description=f"""
        You are a chatbot answering to to all questions concerning the content of a given
        text file.
        The text file has the name {"test2.txt"} and is located at {FILE_DIR}. 
        You are not allowed to write or modify any files. You are only allowed to read files from {FILE_DIR}. 
        The user will give you instructions on what questions to answer.
        When you write the answers, you will need to ensure that the
        user's expectations are met. Remember, you are an accurate and experianced author 
        and you write unique and short answers aligned with the content of the given text file.
        You should use friendly, easy to read language, but stay correct and focussed.
        The answers should not have more than 10 sentences.
        """, 
        tools=[
            marvin.tools.filesystem.ReadFile(root_dir=FILE_DIR),
            #marvin.tools.shell.Shell(
            #require_confirmation=True, working_directory=FILE_DIR
            #)
        ], 
        
        )

    #     
    response = qa(question)
    print(response)

    # We'll return the response, along with the updated state.
    return response.content
