from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import uuid

from app.database import get_db
from app.models.user import User
from app.auth.dependencies import require_role
from app.schemas.question import QuestionCreate, QuestionOut, AIGenRequest
from app.repositories.question_repo import QuestionRepository
from app.services.ai_gen_service import AIGenService
from app.redis_client import get_redis

router = APIRouter(prefix="/questions", tags=["Questions"])

q_repo = QuestionRepository()
ai_service = AIGenService(q_repo)

@router.post("/", response_model=QuestionOut)
async def create_question(
    question: QuestionCreate,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    return await q_repo.create(question, ai_generated=False, reviewed=True, db=db)

@router.get("/{id}", response_model=QuestionOut)
async def get_question(
    id: uuid.UUID,
    user: User = Depends(require_role("student", "instructor", "reviewer", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    question = await q_repo.get_by_id(id, db)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

@router.put("/{id}", response_model=QuestionOut)
async def update_question(
    id: uuid.UUID,
    question: QuestionCreate,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    updated = await q_repo.update(id, question.model_dump(), db)
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated

@router.patch("/{id}", response_model=QuestionOut)
async def partial_update_question(
    id: uuid.UUID,
    data: dict,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    updated = await q_repo.update(id, data, db)
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_question(
    id: uuid.UUID,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    await q_repo.soft_delete(id, db)

@router.get("/bank/list", response_model=List[QuestionOut])
async def list_questions(
    skip: int = 0, limit: int = 100,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    return await q_repo.get_paginated(skip, limit, db)

@router.post("/generate", response_model=QuestionOut)
async def generate_question(
    request: AIGenRequest,
    user: User = Depends(require_role("instructor", "super_admin")),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    # This requires ai_gen_service implementation
    return await ai_service.generate_and_save(
        topic=request.topic,
        difficulty=request.difficulty,
        db=db,
        redis=redis,
        type=request.type.value,
        subtopic=request.subtopic,
        user_id=user.id
    )

@router.patch("/{id}/review", response_model=QuestionOut)
async def review_question(
    id: uuid.UUID,
    user: User = Depends(require_role("reviewer", "super_admin")),
    db: AsyncSession = Depends(get_db)
):
    updated = await q_repo.update(id, {"reviewed": True}, db)
    if not updated:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated
