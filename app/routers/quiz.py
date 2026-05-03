from fastapi import APIRouter, Depends, HTTPException, status, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any
import uuid

from app.database import get_db
from app.redis_client import get_redis
from app.models.user import User
from app.auth.dependencies import require_role
from app.schemas.quiz import QuizStartRequest, AnswerSubmit, AnswerResponse
from app.schemas.question import QuestionOut
from app.schemas.score import ScoreReport

from app.repositories.session_repo import SessionRepository
from app.repositories.answer_repo import AnswerRepository
from app.repositories.question_repo import QuestionRepository
from app.services.evaluation_service import EvaluationService
from app.services.question_service import QuestionService
from app.services.score_service import ScoreService
from app.services.ai_gen_service import AIGenService

router = APIRouter(prefix="/quiz", tags=["Quiz"])

sess_repo = SessionRepository()
ans_repo = AnswerRepository()
q_repo = QuestionRepository()
ai_service = AIGenService(q_repo)
eval_service = EvaluationService(q_repo, ans_repo, sess_repo)
q_service = QuestionService(q_repo, ans_repo, sess_repo, ai_service)
score_service = ScoreService(ans_repo, sess_repo)

def verify_session_owner(session_id: uuid.UUID, user: User, session):
    '''Students can only access their own sessions.'''
    if user.role == 'student' and str(session.user_id) != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, 'Access denied: not your session')

@router.post("/start")
async def start_quiz(
    payload: QuizStartRequest,
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await sess_repo.create(
        user_id=user.id,
        topic=payload.topic,
        config=payload.config,
        course_id=payload.course_id,
        week_id=payload.week_id,
        db=db
    )
    first_question = await q_service.get_next_question(session.id, db, redis)
    return {"session_id": session.id, "question": first_question}

@router.get("/question/{session_id}")
async def get_next_question(
    session_id: uuid.UUID,
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await sess_repo.get(session_id, db)
    if not session:
        raise HTTPException(404, "Session not found")
    verify_session_owner(session_id, user, session)
    question = await q_service.get_next_question(session_id, db, redis)
    return {"question": question, "difficulty_level": session.difficulty}

@router.post("/answer", response_model=AnswerResponse)
async def submit_answer(
    payload: AnswerSubmit,
    user: User = Depends(require_role("student", "instructor", "super_admin")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await sess_repo.get(payload.session_id, db)
    if not session:
        raise HTTPException(404, "Session not found")
    verify_session_owner(payload.session_id, user, session)
    return await eval_service.evaluate_answer(
        payload.session_id, payload.question_id,
        payload.selected_option, payload.time_taken_s, db, redis
    )

@router.post("/submit", response_model=ScoreReport)
async def submit_quiz(
    payload: Dict[str, str],
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session_id_str = payload.get("session_id")
    if not session_id_str:
        raise HTTPException(400, "session_id required")
    session_id = uuid.UUID(session_id_str)
    
    session = await sess_repo.get(session_id, db)
    if not session:
        raise HTTPException(404, "Session not found")
    verify_session_owner(session_id, user, session)
    
    return await score_service.compute_score(session_id, db, redis, background_tasks)

@router.get("/result/{session_id}", response_model=ScoreReport)
async def get_quiz_result(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_role("student", "instructor")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    session = await sess_repo.get(session_id, db)
    if not session:
        raise HTTPException(404, "Session not found")
    if user.role == 'student':
        verify_session_owner(session_id, user, session)
        
    cached = await redis.get(f'score:{session_id}')
    if cached:
        return ScoreReport.model_validate_json(cached)
    
    # If not in cache, fallback to compute
    return await score_service.compute_score(session_id, db, redis, background_tasks)

@router.get("/report/{session_id}/pdf")
async def get_pdf_report(
    session_id: uuid.UUID,
    user: User = Depends(require_role("student", "instructor")),
    db: AsyncSession = Depends(get_db)
):
    session = await sess_repo.get(session_id, db)
    if not session:
        raise HTTPException(404, "Session not found")
    if user.role == 'student':
        verify_session_owner(session_id, user, session)
        
    if not session.report_pdf:
        raise HTTPException(404, "PDF report not yet generated")
        
    return Response(content=session.report_pdf, media_type="application/pdf")

