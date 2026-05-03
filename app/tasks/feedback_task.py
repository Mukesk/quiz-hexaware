import uuid
from app.database import AsyncSessionLocal
from sqlalchemy import update
from app.models.quiz_session import QuizSession
from app.config import settings

if settings.OPENAI_API_KEY.startswith("mock"):
    class MockOpenAI:
        class Chat:
            class Completions:
                async def create(self, **kwargs):
                    class ChoiceMessage:
                        content = "This is a mock feedback. Keep up the good work!"
                    class Choice:
                        message = ChoiceMessage()
                    class MockResponse:
                        choices = [Choice()]
                    return MockResponse()
        chat = Chat()
    openai_client = MockOpenAI()
else:
    from openai import AsyncOpenAI
    from langsmith import wrappers
    openai_client = wrappers.wrap_openai(AsyncOpenAI(api_key=settings.OPENAI_API_KEY))

async def generate_ai_feedback(session_id: uuid.UUID, score_pct: float, breakdown: list, weak: list, strong: list):
    try:
        prompt = f'''
        Student scored {score_pct:.0f}% on quiz.
        Strong areas: {', '.join(strong) if strong else 'None'}.
        Weak areas:   {', '.join(weak) if weak else 'None'}.
        Write 3 sentences of constructive feedback. Be specific about weak areas.
        Suggest next steps. Do not mention the score number.
        '''
        response = await openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL, max_tokens=200, temperature=0.6,
            messages=[
                {'role':'system','content':'You are a constructive learning coach.'},
                {'role':'user','content': prompt}
            ]
        )
        feedback = response.choices[0].message.content.strip()

        # Store in DB
        async with AsyncSessionLocal() as db:
            await db.execute(update(QuizSession)
                .where(QuizSession.id == session_id)
                .values(ai_feedback=feedback))
            await db.commit()
    except Exception as exc:
        print(f"Error generating AI feedback: {exc}")
