import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.question import Question
from app.schemas.question import QuestionCreate
from typing import List, Optional

class QuestionRepository:
    
    async def create(self, q_create: QuestionCreate, ai_generated: bool, reviewed: bool, db: AsyncSession) -> Question:
        question = Question(
            **q_create.model_dump(),
            ai_generated=ai_generated,
            reviewed=reviewed
        )
        db.add(question)
        await db.commit()
        await db.refresh(question)
        return question

    async def get_by_id(self, question_id: uuid.UUID, db: AsyncSession) -> Optional[Question]:
        result = await db.execute(select(Question).where(Question.id == question_id, Question.deleted_at.is_(None)))
        return result.scalar_one_or_none()

    async def update(self, question_id: uuid.UUID, data: dict, db: AsyncSession) -> Optional[Question]:
        stmt = update(Question).where(Question.id == question_id).values(**data).returning(Question)
        result = await db.execute(stmt)
        await db.commit()
        return result.scalar_one_or_none()

    async def soft_delete(self, question_id: uuid.UUID, db: AsyncSession) -> None:
        await db.execute(
            update(Question).where(Question.id == question_id).values(deleted_at=func.now())
        )
        await db.commit()

    async def get_bank_ids(self, topic: str, difficulty: str, db: AsyncSession) -> List[str]:
        result = await db.execute(
            select(Question.id)
            .where(Question.topic == topic)
            .where(Question.difficulty == difficulty)
            .where(Question.deleted_at.is_(None))
            .where(Question.reviewed == True)
            .order_by(func.random())
        )
        return [str(row) for row in result.scalars().all()]
        
    async def get_paginated(self, skip: int, limit: int, db: AsyncSession) -> List[Question]:
        result = await db.execute(
            select(Question)
            .where(Question.deleted_at.is_(None))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def log_ai_gen(self, question_id: uuid.UUID, user_id: uuid.UUID, prompt: str, raw_response: str, tokens: int, cost: float, db: AsyncSession):
        # We will log it in ai_gen_log table later, defined in quiz_session model
        pass
