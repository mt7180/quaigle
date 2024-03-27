from pydantic import BaseModel, Field


class DoubleUploadException(Exception):
    pass


class NoUploadException(Exception):
    pass


class EmptyQuestionException(Exception):
    pass


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

    questions: list[MultipleChoiceQuestion] = []


class ErrorResponse(BaseModel):
    detail: str
