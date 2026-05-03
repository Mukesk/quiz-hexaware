from pydantic import BaseModel, UUID4, field_validator, ValidationInfo
from typing import Optional, List
from enum import Enum
from datetime import datetime

class DifficultyEnum(str, Enum):
    Basic = 'Basic'
    Easy = 'Easy'
    Intermediate = 'Intermediate'
    Advanced = 'Advanced'
    VeryDifficult = 'VeryDifficult'

class QuestionTypeEnum(str, Enum):
    mcq = 'mcq'
    true_false = 'true_false'
    fill_blank = 'fill_blank'
    descriptive = 'descriptive'
    coding = 'coding'
    scenario = 'scenario'

class OptionSchema(BaseModel):
    id: str                        # 'A', 'B', 'C', 'D'
    text: str
    is_correct: bool = False
    explanation: Optional[str] = None

class QuestionCreate(BaseModel):
    topic: str
    subtopic: Optional[str] = None
    difficulty: DifficultyEnum
    type: QuestionTypeEnum
    question_text: str
    options: Optional[List[OptionSchema]] = None
    correct_answer: Optional[str] = None
    rubric: Optional[dict] = None
    test_cases: Optional[list] = None
    blooms_level: Optional[str] = None

    @field_validator('options')
    @classmethod
    def validate_mcq_options(cls, v, info: ValidationInfo):
        if info.data.get('type') == 'mcq':
            if not v or len(v) < 2:
                raise ValueError('MCQ requires at least 2 options')
            if not any(o.is_correct for o in v):
                raise ValueError('MCQ must have at least one correct option')
        return v

class QuestionOut(QuestionCreate):
    id: UUID4
    ai_generated: bool
    reviewed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class AIGenRequest(BaseModel):
    topic: str
    subtopic: Optional[str] = None
    difficulty: DifficultyEnum
    type: QuestionTypeEnum
    blooms_level: Optional[str] = 'Apply'
