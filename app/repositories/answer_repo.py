import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import selectinload
from app.models.user_answer import UserAnswer
from app.models.question import Question
from typing import List

class AnswerRepository:
    async def upsert(self, session_id: uuid.UUID, question_id: uuid.UUID, selected: str, is_correct: bool, time_s: int, db: AsyncSession):
        stmt = insert(UserAnswer).values(
            session_id=session_id, question_id=question_id,
            selected_option=selected, is_correct=is_correct,
            time_taken_s=time_s
        ).on_conflict_do_update(
            index_elements=['session_id', 'question_id'],
            set_={
                'selected_option': selected,
                'is_correct': is_correct,
                'time_taken_s': time_s,
                'answered_at': func.now()
            }
        )
        await db.execute(stmt)
        await db.commit()

    async def get_answered_ids(self, session_id: uuid.UUID, db: AsyncSession) -> List[str]:
        result = await db.execute(select(UserAnswer.question_id).where(UserAnswer.session_id == session_id))
        return [str(row) for row in result.scalars().all()]

    async def get_subtopic_answers(self, session_id: uuid.UUID, subtopic: str, db: AsyncSession) -> List[UserAnswer]:
        result = await db.execute(
            select(UserAnswer)
            .join(Question)
            .where(UserAnswer.session_id == session_id)
            .where(Question.subtopic == subtopic)
        )
        return result.scalars().all()

    async def get_all_with_questions(self, session_id: uuid.UUID, db: AsyncSession) -> List[UserAnswer]:
        result = await db.execute(
            select(UserAnswer)
            .options(selectinload(UserAnswer.question))
            .where(UserAnswer.session_id == session_id)
            .order_by(UserAnswer.answered_at)
        )
        return result.scalars().all()
