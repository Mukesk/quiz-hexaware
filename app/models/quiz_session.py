import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, func, ForeignKey, Index, LargeBinary
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.database import Base

class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id"))
    week_id = Column(UUID(as_uuid=True), ForeignKey("weeks.id"))
    topic = Column(String, nullable=False)
    subtopic = Column(String)
    status = Column(String, default="pending")
    current_q_index = Column(Integer, default=0)
    total_q = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    score_pct = Column(Numeric(5, 2))
    difficulty = Column(String, default="Basic")
    ai_feedback = Column(String)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    config = Column(JSONB)
    report_pdf = Column(LargeBinary)

    __table_args__ = (
        Index("idx_qs_user", "user_id"),
        Index("idx_qs_status", "status"),
        # The prompt mentions PARTITION BY RANGE (started_at), but SQLAlchemy doesn't natively handle table creation with partitions easily.
        # We will handle partitioning in alembic migrations or raw SQL.
    )

class AIGenLog(Base):
    __tablename__ = "ai_gen_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(UUID(as_uuid=True), ForeignKey("questions.id"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    prompt_used = Column(String)
    raw_response = Column(String)
    tokens_used = Column(Integer)
    cost_usd = Column(Numeric(8, 6))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
