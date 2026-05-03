from pydantic import BaseModel, UUID4
from typing import Optional, List

class SubtopicBreakdown(BaseModel):
    subtopic: str
    accuracy_pct: float
    q_count: int
    avg_time_s: float

class AnswerLog(BaseModel):
    q_id: UUID4
    subtopic: Optional[str]
    difficulty: str
    selected: Optional[str]
    correct_answer: str
    is_correct: bool
    time_taken_s: int
    bookmarked: bool
    explanation: Optional[str]

class ScoreReport(BaseModel):
    session_id: UUID4
    user_id: UUID4
    test_name: str
    attempt: int
    status: str          # PASS | FAIL
    score_pct: float
    total_q: int
    correct: int
    final_difficulty: str
    time_taken_s: int
    topic_breakdown: List[SubtopicBreakdown]
    strong_areas: List[str]
    weak_areas: List[str]
    ai_feedback: Optional[str]
    answers: List[AnswerLog]
    completed_at: str
    report_pdf_url: Optional[str]
