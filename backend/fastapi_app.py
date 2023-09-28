# command to run: uvicorn fastapi_app:app --reload
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from marvin import ai_fn, AIApplication
from marvin import settings as marvin_settings
from dotenv import load_dotenv
import pathlib
import os

load_dotenv()
marvin_settings.openai.api_key = os.getenv('OPENAI_API_KEY')

app = FastAPI()

class TextSummary(BaseModel):
    file_name: str
    summary: str

@ai_fn(
    instructions="You are an accurate and experienced copywriter."
)
def summarize_from_string(text: str) -> str:
    """ Please write a unique and short summary of the given text 
    using friendly, easy to read language, but stay correct and focussed. 
    The summary should have at maximum 10 sentences.
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
    
    with open(f"data/{file.filename}", "wb") as f:
        f.write(file.file.read())
    summary_str= await summarize_text(file.filename)
    print(summary_str)
    return TextSummary(
        file_name=file.filename,
        summary= summary_str
    )