import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_
from app.models.question_report import QuestionReport


class ReportRepository:

    async def create(
        self,
        question_id: uuid.UUID,
        session_id:  uuid.UUID,
        reported_by: uuid.UUID,
        reason:      str,
        student_note: Optional[str],
        db: AsyncSession,
    ) -> QuestionReport:
        report = QuestionReport(
            question_id  = question_id,
            session_id   = session_id,
            reported_by  = reported_by,
            reason       = reason,
            student_note = student_note,
        )
        db.add(report)
        await db.commit()
        await db.refresh(report)
        return report

    async def find_existing(
        self,
        question_id: uuid.UUID,
        user_id:     uuid.UUID,
        db:          AsyncSession,
    ) -> Optional[QuestionReport]:
        result = await db.execute(
            select(QuestionReport)
            .where(and_(
                QuestionReport.question_id == question_id,
                QuestionReport.reported_by == user_id,
            ))
            .order_by(QuestionReport.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, report_id: uuid.UUID, db: AsyncSession
    ) -> Optional[QuestionReport]:
        result = await db.execute(
            select(QuestionReport).where(QuestionReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(
        self, status: str, page: int, size: int, db: AsyncSession
    ) -> list[QuestionReport]:
        result = await db.execute(
            select(QuestionReport)
            .where(QuestionReport.status == status)
            .order_by(QuestionReport.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all()

    async def get_by_reporter(
        self, user_id: uuid.UUID, db: AsyncSession
    ) -> list[QuestionReport]:
        result = await db.execute(
            select(QuestionReport)
            .where(QuestionReport.reported_by == user_id)
            .order_by(QuestionReport.created_at.desc())
        )
        return result.scalars().all()

    async def get_by_question(
        self, question_id: uuid.UUID, db: AsyncSession
    ) -> list[QuestionReport]:
        result = await db.execute(
            select(QuestionReport)
            .where(QuestionReport.question_id == question_id)
            .order_by(QuestionReport.created_at.desc())
        )
        return result.scalars().all()

    async def update_status(
        self,
        report_id:      uuid.UUID,
        status:         str,
        db:             AsyncSession,
        verdict:        Optional[str]   = None,
        confidence:     Optional[float] = None,
        replacement_id: Optional[uuid.UUID] = None,
        reviewed_by:    Optional[uuid.UUID] = None,
        reviewer_note:  Optional[str]   = None,
    ) -> None:
        values = {"status": status, "resolved_at": func.now()}
        if verdict        is not None: values["agent_verdict"]    = verdict
        if confidence     is not None: values["agent_confidence"] = confidence
        if replacement_id is not None: values["replacement_q_id"] = replacement_id
        if reviewed_by    is not None: values["reviewed_by"]      = reviewed_by
        if reviewer_note  is not None: values["reviewer_note"]    = reviewer_note

        await db.execute(
            update(QuestionReport)
            .where(QuestionReport.id == report_id)
            .values(**values)
        )
        await db.commit()

    async def get_stats(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(QuestionReport.status, func.count().label("cnt"))
            .group_by(QuestionReport.status)
        )
        by_status = {row.status: row.cnt for row in result.all()}

        reason_result = await db.execute(
            select(QuestionReport.reason, func.count().label("cnt"))
            .group_by(QuestionReport.reason)
        )
        by_reason = {row.reason: row.cnt for row in reason_result.all()}
        return {"by_status": by_status, "by_reason": by_reason}
