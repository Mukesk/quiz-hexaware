import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.session_repo import SessionRepository
from app.repositories.answer_repo import AnswerRepository
from app.repositories.question_repo import QuestionRepository
from app.schemas.quiz import AnswerResponse
from app.utils.adaptive import apply_adaptive_rules
from app.utils.metrics import compute_accuracy

class EvaluationService:
    def __init__(self, q_repo: QuestionRepository, ans_repo: AnswerRepository, sess_repo: SessionRepository):
        self.q_repo = q_repo
        self.ans_repo = ans_repo
        self.sess_repo = sess_repo

    async def evaluate_answer(
        self, session_id: uuid.UUID, question_id: uuid.UUID, selected_option: str, time_taken_s: int, db: AsyncSession, redis
    ) -> AnswerResponse:
        # 1. Fetch question from repo (never trust client for correct_answer)
        question = await self.q_repo.get_by_id(question_id, db)

        # 2. Compute correctness in Python (never ask LLM for this)
        is_correct = (selected_option == question.correct_answer)

        # 3. Upsert to user_answers (idempotent)
        await self.ans_repo.upsert(session_id, question_id, selected_option, is_correct, time_taken_s, db)

        # 4. Update session counter
        await self.sess_repo.increment_correct(session_id, is_correct, db)

        # 5. Run adaptive logic every 5 questions per subtopic
        session = await self.sess_repo.get(session_id, db)
        difficulty_changed, new_difficulty = False, session.difficulty
        subtopic_answers = await self.ans_repo.get_subtopic_answers(session_id, question.subtopic, db)

        if len(subtopic_answers) % 5 == 0 and len(subtopic_answers) > 0:
            accuracy = compute_accuracy(subtopic_answers)  # Python, not LLM
            new_difficulty, difficulty_changed = await apply_adaptive_rules(accuracy, session.difficulty, session_id, db, self.sess_repo)

        # 6. Check if session complete
        session_complete = await self._check_completion(session_id, db)

        explanation = next(
            (o.get('explanation') for o in (question.options or [])
             if o.get('id') == question.correct_answer), None)

        return AnswerResponse(
            is_correct=is_correct,
            correct_answer=question.correct_answer,
            explanation=explanation,
            difficulty_changed=difficulty_changed,
            new_difficulty=new_difficulty if difficulty_changed else None,
            session_complete=session_complete,
        )

    async def _check_completion(self, session_id: uuid.UUID, db: AsyncSession) -> bool:
        session = await self.sess_repo.get(session_id, db)
        return session.current_q_index >= session.config.get('total_q', 10) if session.config else False
