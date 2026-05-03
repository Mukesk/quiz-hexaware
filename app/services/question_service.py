import uuid
import json
import random
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.session_repo import SessionRepository
from app.repositories.answer_repo import AnswerRepository
from app.repositories.question_repo import QuestionRepository
from app.services.ai_gen_service import AIGenService
from app.schemas.question import QuestionOut

class QuestionService:
    def __init__(self, q_repo: QuestionRepository, ans_repo: AnswerRepository, sess_repo: SessionRepository, ai_gen_service: AIGenService):
        self.q_repo = q_repo
        self.ans_repo = ans_repo
        self.sess_repo = sess_repo
        self.ai_gen_service = ai_gen_service

    async def get_next_question(self, session_id: uuid.UUID, db: AsyncSession, redis) -> QuestionOut:
        session = await self.sess_repo.get(session_id, db)
        answered_ids = await self.ans_repo.get_answered_ids(session_id, db)

        # 1. Check Redis cache for question bank
        cache_key = f'question_bank:{session.topic}:{session.difficulty}'
        cached = await redis.get(cache_key)
        if cached:
            bank_ids = json.loads(cached)
        else:
            bank_ids = await self.q_repo.get_bank_ids(session.topic, session.difficulty, db)
            await redis.setex(cache_key, 3600, json.dumps(bank_ids))  # TTL 1hr

        # 2. Filter out already answered
        available = [qid for qid in bank_ids if qid not in answered_ids]

        # 3. AI fallback if bank exhausted
        if not available:
            new_q = await self.ai_gen_service.generate_and_save(
                topic=session.topic,
                difficulty=session.difficulty,
                db=db,
                redis=redis,
                type='mcq',
                user_id=session.user_id
            )
            await redis.delete(cache_key)  # Invalidate cache
            return QuestionOut.model_validate(new_q)

        # 4. Random selection from available
        question_id = random.choice(available)
        question = await self.q_repo.get_by_id(question_id, db)
        return QuestionOut.model_validate(question)
