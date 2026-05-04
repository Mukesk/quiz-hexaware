import uuid
from sqlalchemy import (
    Column, String, Text, Numeric, DateTime,
    func, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class QuestionReport(Base):
    __tablename__ = "question_reports"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # What was reported
    question_id       = Column(UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False)
    session_id        = Column(UUID(as_uuid=True), ForeignKey("quiz_sessions.id"), nullable=False)
    reported_by       = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Report details (from student)
    reason            = Column(Text, nullable=False)
    student_note      = Column(Text)

    # Agent decision
    status            = Column(Text, nullable=False, default="pending")
    agent_verdict     = Column(Text)
    agent_confidence  = Column(Numeric(4, 2))
    replacement_q_id  = Column(UUID(as_uuid=True), ForeignKey("questions.id"))

    # Human override fields
    reviewed_by       = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewer_note     = Column(Text)

    # Timestamps
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at       = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_qr_status",   "status"),
        Index("idx_qr_question", "question_id"),
        Index("idx_qr_reporter", "reported_by"),
    )
