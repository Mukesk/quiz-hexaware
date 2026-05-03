import uuid
from sqlalchemy import Column, String, Boolean, Integer, DateTime, func, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database import Base

class UserAnswer(Base):
    __tablename__ = "user_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    selected_option = Column(String)
    is_correct = Column(Boolean)
    time_taken_s = Column(Integer)
    bookmarked = Column(Boolean, default=False)
    answered_at = Column(DateTime(timezone=True), server_default=func.now())

    # Define relationships for fetching joins
    question = relationship("Question")
    session = relationship("QuizSession")

    __table_args__ = (
        UniqueConstraint("session_id", "question_id", name="uq_session_question"),
        Index("idx_ua_session", "session_id"),
        Index("idx_ua_bookmarked", "session_id", postgresql_where=bookmarked.is_(True)),
    )
