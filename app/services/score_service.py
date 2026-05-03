import uuid
import json
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.session_repo import SessionRepository
from app.repositories.answer_repo import AnswerRepository
from app.schemas.score import ScoreReport, SubtopicBreakdown, AnswerLog
from fastapi import BackgroundTasks

class ScoreService:
    def __init__(self, ans_repo: AnswerRepository, sess_repo: SessionRepository):
        self.ans_repo = ans_repo
        self.sess_repo = sess_repo

    async def compute_score(self, session_id: uuid.UUID, db: AsyncSession, redis, background_tasks: BackgroundTasks) -> ScoreReport:
        session = await self.sess_repo.get(session_id, db)
        answers = await self.ans_repo.get_all_with_questions(session_id, db)

        # All computations in Python — NEVER ask LLM to calculate these
        total_q     = len(answers)
        correct     = sum(1 for a in answers if a.is_correct)
        score_pct   = round(correct / total_q * 100, 2) if total_q else 0.0
        total_time  = sum(a.time_taken_s or 0 for a in answers)

        # Subtopic breakdown
        subtopics = {}
        for a in answers:
            st = a.question.subtopic or session.topic
            subtopics.setdefault(st, {'correct':0,'total':0,'time':0})
            subtopics[st]['total']   += 1
            subtopics[st]['correct'] += int(a.is_correct)
            subtopics[st]['time']    += a.time_taken_s or 0

        breakdown = [
            SubtopicBreakdown(
                subtopic=st,
                accuracy_pct=round(v['correct']/v['total']*100,2),
                q_count=v['total'],
                avg_time_s=round(v['time']/v['total'],1)
            ) for st, v in subtopics.items()
        ]
        strong = [b.subtopic for b in breakdown if b.accuracy_pct >= 80]
        weak   = [b.subtopic for b in breakdown if b.accuracy_pct <  50]

        # Update session with computed score
        await self.sess_repo.finalise(
            session_id, score_pct=score_pct,
            status='completed', db=db
        )

        # Trigger background tasks (non-blocking)
        # Import dynamically to avoid circular imports if needed
        from app.tasks.feedback_task import generate_ai_feedback
        from app.tasks.pdf_task import generate_pdf_report
        background_tasks.add_task(generate_ai_feedback, session_id, score_pct, [b.model_dump() for b in breakdown], weak, strong)
        background_tasks.add_task(generate_pdf_report, session_id, redis)

        answer_logs = [
            AnswerLog(
                q_id=a.question_id,
                subtopic=a.question.subtopic,
                difficulty=a.question.difficulty,
                selected=a.selected_option,
                correct_answer=a.question.correct_answer,
                is_correct=a.is_correct,
                time_taken_s=a.time_taken_s or 0,
                bookmarked=a.bookmarked,
                explanation=next((o.get('explanation') for o in (a.question.options or []) if o.get('id') == a.question.correct_answer), None)
            ) for a in answers
        ]

        # Cache ScoreReport in Redis permanently
        report = ScoreReport(
            session_id=session_id, user_id=session.user_id,
            score_pct=score_pct, total_q=total_q, correct=correct,
            status='PASS' if score_pct >= 60 else 'FAIL',
            topic_breakdown=breakdown, strong_areas=strong, weak_areas=weak,
            time_taken_s=total_time, final_difficulty=session.difficulty,
            answers=answer_logs,
            test_name=session.topic, attempt=1,
            ai_feedback=None, report_pdf_url=f"/quiz/report/{session_id}/pdf",
            completed_at=str(session.completed_at) if session.completed_at else "",
        )
        await redis.set(f'score:{session_id}', report.model_dump_json())
        return report
