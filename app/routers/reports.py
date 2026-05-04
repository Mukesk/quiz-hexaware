import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database import get_db
from app.redis_client import get_redis
from app.models.user import User
from app.auth.dependencies import require_role
from app.schemas.report import (
    QuestionReportCreate, QuestionReportAck, QuestionReportOut,
    ReviewerOverride, ReportStats,
)
from app.repositories.report_repo import ReportRepository
from app.repositories.question_repo import QuestionRepository
from app.repositories.session_repo import SessionRepository
from app.services.report_service import ReportService

router = APIRouter(tags=["Question Reports"])

report_repo   = ReportRepository()
question_repo = QuestionRepository()
session_repo  = SessionRepository()
report_service = ReportService(report_repo, question_repo, session_repo)


def _to_out(r) -> QuestionReportOut:
    return QuestionReportOut(
        id               = r.id,
        question_id      = r.question_id,
        session_id       = r.session_id,
        reported_by      = r.reported_by,
        reason           = r.reason,
        student_note     = r.student_note,
        status           = r.status,
        agent_verdict    = r.agent_verdict,
        agent_confidence = float(r.agent_confidence) if r.agent_confidence else None,
        replacement_q_id = r.replacement_q_id,
        reviewed_by      = r.reviewed_by,
        reviewer_note    = r.reviewer_note,
        created_at       = str(r.created_at),
        resolved_at      = str(r.resolved_at) if r.resolved_at else None,
    )


# ── Student: submit a report ────────────────────────────────────────────
@router.post("/quiz/report", response_model=QuestionReportAck)
async def report_question(
    payload:          QuestionReportCreate,
    background_tasks: BackgroundTasks,
    current_user:     User         = Depends(require_role("student", "instructor", "admin")),
    db:               AsyncSession = Depends(get_db),
    redis                          = Depends(get_redis),
):
    return await report_service.submit_report(
        payload, current_user, db, background_tasks, redis
    )


# ── Student: view their own submitted reports ────────────────────────────
@router.get("/quiz/report/my", response_model=List[QuestionReportAck])
async def my_reports(
    current_user: User         = Depends(require_role("student")),
    db:           AsyncSession = Depends(get_db),
):
    reports = await report_repo.get_by_reporter(current_user.id, db)
    return [
        QuestionReportAck(
            report_id = r.id,
            status    = r.status,
            message   = f"Report filed on question {r.question_id}",
        )
        for r in reports
    ]


# ── Reviewer: list all reports (filterable by status) ───────────────────
@router.get("/questions/reports", response_model=List[QuestionReportOut])
async def list_reports(
    status:       str         = "pending",
    page:         int         = 1,
    size:         int         = 20,
    current_user: User         = Depends(require_role("instructor", "admin")),
    db:           AsyncSession = Depends(get_db),
):
    reports = await report_repo.get_by_status(status, page, size, db)
    return [_to_out(r) for r in reports]


# ── Reviewer: get single report detail ──────────────────────────────────
@router.get("/questions/reports/{report_id}", response_model=QuestionReportOut)
async def get_report(
    report_id:    uuid.UUID,
    current_user: User         = Depends(require_role("instructor", "admin")),
    db:           AsyncSession = Depends(get_db),
):
    report = await report_repo.get_by_id(report_id, db)
    if not report:
        raise HTTPException(404, "Report not found")
    return _to_out(report)


# ── Reviewer: human override ─────────────────────────────────────────────
@router.patch("/questions/reports/{report_id}/override", response_model=QuestionReportOut)
async def override_report(
    report_id:    uuid.UUID,
    payload:      ReviewerOverride,
    current_user: User         = Depends(require_role("instructor", "admin")),
    db:           AsyncSession = Depends(get_db),
):
    return await report_service.human_override(report_id, payload, current_user, db)


# ── Reviewer: get all reports for a specific question ───────────────────
@router.get("/questions/{question_id}/reports", response_model=List[QuestionReportOut])
async def reports_for_question(
    question_id:  uuid.UUID,
    current_user: User         = Depends(require_role("instructor", "admin")),
    db:           AsyncSession = Depends(get_db),
):
    reports = await report_repo.get_by_question(question_id, db)
    return [_to_out(r) for r in reports]


# ── Admin: aggregate stats ───────────────────────────────────────────────
@router.get("/questions/reports/stats", response_model=ReportStats)
async def report_stats(
    current_user: User         = Depends(require_role("admin")),
    db:           AsyncSession = Depends(get_db),
):
    raw = await report_repo.get_stats(db)
    by_status = raw.get("by_status", {})
    return ReportStats(
        total          = sum(by_status.values()),
        pending        = by_status.get("pending", 0),
        agent_reviewing= by_status.get("agent_reviewing", 0),
        valid_replaced = by_status.get("valid_replaced", 0),
        valid_edited   = by_status.get("valid_edited", 0),
        rejected       = by_status.get("rejected", 0),
        human_override = by_status.get("human_override", 0),
        by_reason      = raw.get("by_reason", {}),
    )
