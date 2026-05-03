import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.quiz_session import QuizSession
from typing import Optional

class SessionRepository:
    async def create(self, user_id: uuid.UUID, topic: str, config: dict, course_id: Optional[uuid.UUID], week_id: Optional[uuid.UUID], db: AsyncSession) -> QuizSession:
        session = QuizSession(
            user_id=user_id,
            topic=topic,
            config=config,
            course_id=course_id,
            week_id=week_id,
            status="in_progress"
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get(self, session_id: uuid.UUID, db: AsyncSession) -> Optional[QuizSession]:
        result = await db.execute(select(QuizSession).where(QuizSession.id == session_id))
        return result.scalar_one_or_none()

    async def update_difficulty(self, session_id: uuid.UUID, new_difficulty: str, db: AsyncSession):
        await db.execute(
            update(QuizSession).where(QuizSession.id == session_id).values(difficulty=new_difficulty)
        )
        await db.commit()

    async def increment_correct(self, session_id: uuid.UUID, is_correct: bool, db: AsyncSession):
        session = await self.get(session_id, db)
        if session:
            await db.execute(
                update(QuizSession)
                .where(QuizSession.id == session_id)
                .values(
                    current_q_index=session.current_q_index + 1,
                    correct=session.correct + (1 if is_correct else 0)
                )
            )
            await db.commit()

    async def finalise(self, session_id: uuid.UUID, score_pct: float, status: str, db: AsyncSession):
        from sqlalchemy import func
        await db.execute(
            update(QuizSession)
            .where(QuizSession.id == session_id)
            .values(
                score_pct=score_pct,
                status=status,
                completed_at=func.now()
            )
        )
        await db.commit()
