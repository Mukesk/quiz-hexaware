import uuid
import json
import logging
from sqlalchemy import update, select

from app.database import AsyncSessionLocal
from app.models.question_report import QuestionReport
from app.models.question import Question
from app.schemas.report import AgentDecision

logger = logging.getLogger(__name__)


async def review_question_report(report_id: uuid.UUID, redis) -> None:
    """
    Async background task: runs the LangChain ReviewAgent on a flagged question.
    Fired by FastAPI BackgroundTasks after POST /quiz/report.
    Never blocks the student's quiz session.
    """
    async with AsyncSessionLocal() as db:
        try:
            # 1. Fetch report + question
            report_result = await db.execute(
                select(QuestionReport).where(QuestionReport.id == report_id)
            )
            report = report_result.scalar_one_or_none()
            if not report:
                logger.error(f"Report not found: {report_id}")
                return

            question_result = await db.execute(
                select(Question).where(Question.id == report.question_id)
            )
            question = question_result.scalar_one_or_none()
            if not question:
                logger.error(f"Question not found for report: {report_id}")
                return

            # 2. Mark as agent_reviewing
            await db.execute(
                update(QuestionReport)
                .where(QuestionReport.id == report_id)
                .values(status="agent_reviewing")
            )
            await db.commit()

            # 3. Build agent input
            question_json = json.dumps({
                "id":             str(question.id),
                "question_text":  question.question_text,
                "type":           question.type,
                "options":        question.options,
                "correct_answer": question.correct_answer,
                "topic":          question.topic,
                "subtopic":       question.subtopic,
                "difficulty":     question.difficulty,
            })
            agent_input = (
                f"Question: {question_json}\n"
                f"Report reason: {report.reason}\n"
                f"Student note: {report.student_note or '(none)'}\n"
                f"Please review and take appropriate action. "
                f"Return a final JSON summary with keys: action, confidence, verdict, is_valid, edited_fields."
            )

            # 4. Run agent
            from app.services.review_agent import build_review_agent
            agent = build_review_agent()
            raw_result = await agent.ainvoke({"input": agent_input})
            output = raw_result.get("output", "{}")

            # 5. Parse agent decision
            try:
                # Strip markdown code blocks if present
                clean = output.strip()
                if clean.startswith("```"):
                    clean = clean.split("```")[1]
                    if clean.startswith("json"):
                        clean = clean[4:]
                parsed = json.loads(clean)
                decision = AgentDecision(**parsed)
            except Exception as e:
                logger.error(f"Agent output parse failed: {e} | output: {output}")
                await db.execute(
                    update(QuestionReport)
                    .where(QuestionReport.id == report_id)
                    .values(
                        status="rejected",
                        agent_verdict=f"Agent output unparseable: {output[:500]}",
                    )
                )
                await db.commit()
                return

            # 6. Execute decision
            if decision.action == "replace" and decision.is_valid:
                await _replace_question(db, report, question, decision, redis)
            elif decision.action == "edit" and decision.is_valid:
                await _edit_question(db, report, question, decision)
            else:
                await db.execute(
                    update(QuestionReport)
                    .where(QuestionReport.id == report_id)
                    .values(
                        status="rejected",
                        agent_verdict=decision.verdict,
                        agent_confidence=decision.confidence,
                    )
                )
                await db.commit()

            logger.info(f"Report {report_id} resolved: {decision.action}")

        except Exception as exc:
            logger.error(f"review_question_report task failed: {exc}")
            try:
                await db.execute(
                    update(QuestionReport)
                    .where(QuestionReport.id == report_id)
                    .values(status="rejected", agent_verdict=f"Task error: {str(exc)[:300]}")
                )
                await db.commit()
            except Exception:
                pass


async def _replace_question(db, report, original_q, decision: AgentDecision, redis) -> None:
    """Full replacement: archive original, insert corrected question."""
    fields = decision.edited_fields or {}

    new_q = Question(
        topic          = original_q.topic,
        subtopic       = original_q.subtopic,
        difficulty     = original_q.difficulty,
        type           = original_q.type,
        blooms_level   = original_q.blooms_level,
        question_text  = fields.get("question_text", original_q.question_text),
        options        = fields.get("options", original_q.options),
        correct_answer = fields.get("correct_answer", original_q.correct_answer),
        ai_generated   = True,
        reviewed       = True,   # agent-approved
        is_active      = True,
    )
    db.add(new_q)
    await db.flush()   # get new_q.id before commit

    # Archive original
    await db.execute(
        update(Question)
        .where(Question.id == original_q.id)
        .values(is_active=False, replaced_by=new_q.id)
    )

    # Update report
    await db.execute(
        update(QuestionReport)
        .where(QuestionReport.id == report.id)
        .values(
            status="valid_replaced",
            agent_verdict=decision.verdict,
            agent_confidence=decision.confidence,
            replacement_q_id=new_q.id,
        )
    )
    await db.commit()

    # Invalidate Redis cache for this topic+difficulty
    if redis:
        cache_key = f"question_bank:{original_q.topic}:{original_q.difficulty}"
        await redis.delete(cache_key)
        logger.info(f"Redis cache invalidated: {cache_key}")


async def _edit_question(db, report, question, decision: AgentDecision) -> None:
    """Minor in-place edit: fix specific fields without creating a new row."""
    fields = decision.edited_fields or {}
    updates = {}
    if "correct_answer" in fields: updates["correct_answer"] = fields["correct_answer"]
    if "question_text"  in fields: updates["question_text"]  = fields["question_text"]
    if "options"        in fields: updates["options"]         = fields["options"]

    if updates:
        await db.execute(
            update(Question).where(Question.id == question.id).values(**updates)
        )

    await db.execute(
        update(QuestionReport)
        .where(QuestionReport.id == report.id)
        .values(
            status="valid_edited",
            agent_verdict=decision.verdict,
            agent_confidence=decision.confidence,
        )
    )
    await db.commit()
