import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class Question(Base):
    __tablename__ = "questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    topic = Column(String, nullable=False)
    subtopic = Column(String)
    difficulty = Column(String, nullable=False)
    type = Column(String, nullable=False)
    question_text = Column(String, nullable=False)
    options = Column(JSONB)
    correct_answer = Column(String)
    rubric = Column(JSONB)
    test_cases = Column(JSONB)
    blooms_level = Column(String)
    ai_generated = Column(Boolean, default=False)
    reviewed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, nullable=False)
    replaced_by = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=True)
    report_count = Column(Integer, default=0)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_q_topic_diff", "topic", "difficulty", postgresql_where=deleted_at.is_(None)),
        Index("idx_q_ai", "ai_generated", "reviewed"),
        Index("idx_q_options_gin", "options", postgresql_using="gin"),
        Index("idx_q_active", "is_active"),
    )
