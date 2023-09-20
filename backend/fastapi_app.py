# command to run: uvicorn fastapi_app:app --reload
from fastapi import FastAPI, UploadFile
from pydantic import BaseModel
from marvin import ai_fn, AIApplication
from marvin import settings as marvin_settings
from dotenv import load_dotenv
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
def summarize_from_string(file_name: str) -> str:
    """ Please write a unique and short summary of the following text 
    using friendly, easy to read language, but stay correct and focussed. 
    The summary should have at maximum 10 sentences.
    """
    # noqa: E501


async def summarize_text(file_name: str) -> str:
    data_path = "./data"
    with open(os.path.join(data_path, file_name),"r") as f:
        text = " ".join(f.read().split('\n'))
    return summarize_from_string(text)

    

# AIApplication:
# - give different ai-functions 
# - make ai_models & pydantic classes for QueryDocument QAQuestion QAResponse
# - try to use state to save the embeddings v-db, otherwise: create and save vectorstore as with marvin-recipes
# - first try text-doc, later on pdf etc

# @app.get("/qa_text")
# def run(question: str, state:  {}) -> QAResponse:
#     description = (
#         "A chatbot. Users will ask questions concerning a given text. "
#         
#     )

#     qa = AIApplication(state=state, description=description, functions.., state ..)

#     
#     response = qa(question)

#     # We'll return the response, along with the updated state.
#     return QAResponse(content=response.content, state={})


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


# @app.post("/qa_text/")
# @ai_fn
# def qa_text(file_name: str) -> dict:
#     pass

# @app.post("/summarize_data/")
# @ai_fn
# def summarize_data(file_name: str) -> dict:
#     pass