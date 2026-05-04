import uuid
from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.report_repo import ReportRepository
from app.repositories.question_repo import QuestionRepository
from app.repositories.session_repo import SessionRepository
from app.models.user import User
from app.schemas.report import (
    QuestionReportCreate, QuestionReportAck, QuestionReportOut,
    ReportStatus, ReviewerOverride,
)


class ReportService:

    def __init__(
        self,
        report_repo:   ReportRepository,
        question_repo: QuestionRepository,
        session_repo:  SessionRepository,
    ):
        self.report_repo   = report_repo
        self.question_repo = question_repo
        self.session_repo  = session_repo

    async def submit_report(
        self,
        payload:          QuestionReportCreate,
        current_user:     User,
        db:               AsyncSession,
        background_tasks: BackgroundTasks,
        redis,
    ) -> QuestionReportAck:

        # 1. Validate session belongs to the requesting student
        session = await self.session_repo.get(payload.session_id, db)
        if not session:
            raise HTTPException(404, "Session not found")
        if str(session.user_id) != str(current_user.id):
            raise HTTPException(403, "Not your session")

        # 2. Validate question exists and is active
        question = await self.question_repo.get_by_id(payload.question_id, db)
        if not question:
            raise HTTPException(404, "Question not found or no longer active")

        # 3. Prevent duplicate active reports (same student, same question)
        existing = await self.report_repo.find_existing(
            payload.question_id, current_user.id, db
        )
        if existing and existing.status not in ("rejected",):
            raise HTTPException(409, "You already reported this question")

        # 4. Save report
        report = await self.report_repo.create(
            question_id  = payload.question_id,
            session_id   = payload.session_id,
            reported_by  = current_user.id,
            reason       = payload.reason.value,
            student_note = payload.student_note,
            db           = db,
        )

        # 5. Increment report_count on question (for monitoring)
        await self.question_repo.increment_report_count(payload.question_id, db)

        # 6. Fire background task — NEVER await, never block student
        from app.tasks.review_task import review_question_report
        background_tasks.add_task(review_question_report, report.id, redis)

        # 7. Return immediately
        return QuestionReportAck(
            report_id = report.id,
            status    = ReportStatus.pending,
            message   = "Your report has been received and is under review.",
        )

    async def human_override(
        self,
        report_id:    uuid.UUID,
        payload:      ReviewerOverride,
        current_user: User,
        db:           AsyncSession,
    ) -> QuestionReportOut:
        report = await self.report_repo.get_by_id(report_id, db)
        if not report:
            raise HTTPException(404, "Report not found")

        if payload.action == "reject":
            await self.report_repo.update_status(
                report_id     = report_id,
                status        = "human_override",
                db            = db,
                reviewed_by   = current_user.id,
                reviewer_note = (payload.reviewer_note or "") + " [REJECTED by reviewer]",
            )
        elif payload.action in ("accept_replace", "accept_edit"):
            # If reviewer provides edited question fields, apply them
            if payload.edited_question and payload.action == "accept_edit":
                from sqlalchemy import update
                from app.models.question import Question
                await db.execute(
                    update(Question)
                    .where(Question.id == report.question_id)
                    .values(**{
                        k: v for k, v in payload.edited_question.items()
                        if k in ("question_text", "correct_answer", "options")
                    })
                )
                await db.commit()

            await self.report_repo.update_status(
                report_id     = report_id,
                status        = "human_override",
                db            = db,
                reviewed_by   = current_user.id,
                reviewer_note = payload.reviewer_note,
            )
        else:
            raise HTTPException(400, f"Unknown action: {payload.action}")

        updated = await self.report_repo.get_by_id(report_id, db)
        return QuestionReportOut(
            id               = updated.id,
            question_id      = updated.question_id,
            session_id       = updated.session_id,
            reported_by      = updated.reported_by,
            reason           = updated.reason,
            student_note     = updated.student_note,
            status           = updated.status,
            agent_verdict    = updated.agent_verdict,
            agent_confidence = float(updated.agent_confidence) if updated.agent_confidence else None,
            replacement_q_id = updated.replacement_q_id,
            reviewed_by      = updated.reviewed_by,
            reviewer_note    = updated.reviewer_note,
            created_at       = str(updated.created_at),
            resolved_at      = str(updated.resolved_at) if updated.resolved_at else None,
        )
