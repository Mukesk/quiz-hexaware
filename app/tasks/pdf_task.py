import uuid
from app.database import AsyncSessionLocal
from sqlalchemy import update
from app.models.quiz_session import QuizSession
from app.schemas.score import ScoreReport

def build_score_pdf(report: ScoreReport) -> bytes:
    # Dummy report generation since we lack full ReportLab setup details
    return b"%PDF-1.4\n%Mock PDF Content"

async def generate_pdf_report(session_id: uuid.UUID, redis):
    try:
        # 1. Fetch ScoreReport from Redis
        raw = await redis.get(f'score:{session_id}')
        if not raw:
            return "Report not found in cache"
            
        report = ScoreReport.model_validate_json(raw)

        # 2. Build PDF with ReportLab
        pdf_bytes = build_score_pdf(report)

        # 3. Store PDF in PostgreSQL Database directly
        async with AsyncSessionLocal() as db:
            await db.execute(update(QuizSession)
                .where(QuizSession.id == session_id)
                .values(report_pdf=pdf_bytes))
            await db.commit()
    except Exception as exc:
        print(f"Error generating PDF report: {exc}")
