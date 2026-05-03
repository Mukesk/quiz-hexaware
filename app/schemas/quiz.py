from pydantic import BaseModel, UUID4
from typing import Optional

class QuizStartRequest(BaseModel):
    course_id: Optional[UUID4] = None
    week_id: Optional[UUID4] = None
    topic: str
    config: Optional[dict] = {}    # {timer_mins, shuffle, allow_retake}

class AnswerSubmit(BaseModel):
    session_id: UUID4
    question_id: UUID4
    selected_option: str
    time_taken_s: int

class AnswerResponse(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: Optional[str] = None
    difficulty_changed: bool
    new_difficulty: Optional[str] = None
    session_complete: bool
