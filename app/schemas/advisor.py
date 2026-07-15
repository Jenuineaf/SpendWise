from pydantic import BaseModel, Field


class AdvisorQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AdvisorAnswer(BaseModel):
    answer: str
