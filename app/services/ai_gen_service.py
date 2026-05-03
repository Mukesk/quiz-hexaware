import json
import uuid
from fastapi import HTTPException
from pydantic import ValidationError
from app.schemas.question import QuestionCreate
from app.repositories.question_repo import QuestionRepository
from app.config import settings

# Setup OpenAI mock or actual client
if settings.OPENAI_API_KEY.startswith("mock"):
    class MockOpenAI:
        class Chat:
            class Completions:
                async def create(self, **kwargs):
                    class ChoiceMessage:
                        content = json.dumps({
                            "question_text": "What is the capital of France?",
                            "options": [
                                {"id": "A", "text": "Paris", "is_correct": True, "explanation": "Paris is the capital of France."},
                                {"id": "B", "text": "London", "is_correct": False, "explanation": ""},
                                {"id": "C", "text": "Berlin", "is_correct": False, "explanation": ""},
                                {"id": "D", "text": "Madrid", "is_correct": False, "explanation": ""}
                            ],
                            "correct_answer": "A",
                            "explanation": "Paris is the capital of France."
                        })
                    class Choice:
                        message = ChoiceMessage()
                    class Usage:
                        total_tokens = 100
                    class MockResponse:
                        choices = [Choice()]
                        usage = Usage()
                    return MockResponse()
        chat = Chat()
    openai_client = MockOpenAI()
else:
    from openai import AsyncOpenAI
    from langsmith import wrappers
    openai_client = wrappers.wrap_openai(AsyncOpenAI(api_key=settings.OPENAI_API_KEY))


class AIGenService:
    PROMPT_TEMPLATE = '''
    Generate 1 {difficulty} level {type} question on topic: {topic},
    subtopic: {subtopic}. Bloom's level: {blooms_level}.
    Return ONLY valid JSON (no markdown, no preamble):
    {{
      "question_text": "str",
      "options": [{{"id":"str", "text":"str", "is_correct":true, "explanation":"str"}}],
      "correct_answer": "str",
      "explanation": "str"
    }}
    '''

    def __init__(self, q_repo: QuestionRepository):
        self.q_repo = q_repo

    async def generate_and_save(
        self, topic: str, difficulty: str, db, redis, type='mcq', subtopic=None, user_id=None
    ):
        # 1. Rate limit check (Redis token bucket)
        if user_id:
            count = await redis.incr(f'ratelimit:ai:{user_id}')
            if count == 1:
                await redis.expire(f'ratelimit:ai:{user_id}', 3600)
            if count > 20:
                raise HTTPException(429, 'AI generation rate limit exceeded')

        # 2. Build prompt
        prompt = self.PROMPT_TEMPLATE.format(
            difficulty=difficulty, type=type, topic=topic,
            subtopic=subtopic or topic, blooms_level='Apply'
        )

        # 3. Call GPT-4o-mini
        try:
            response = await openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                response_format={'type': 'json_object'},
                max_tokens=400,
                messages=[
                    {'role':'system','content':'You are an expert question generator. Return only valid JSON.'},
                    {'role':'user','content': prompt}
                ]
            )
        except Exception as e:
            err_str = str(e)
            if '401' in err_str or 'invalid_api_key' in err_str or 'AuthenticationError' in err_str:
                raise HTTPException(502, 'OpenAI API key is invalid or expired. Please update OPENAI_API_KEY in .env.')
            elif '429' in err_str or 'RateLimitError' in err_str:
                raise HTTPException(429, 'OpenAI rate limit exceeded. Please try again later.')
            else:
                raise HTTPException(502, f'OpenAI API error: {err_str}')

        raw = response.choices[0].message.content
        tokens = response.usage.total_tokens

        # 4. Validate with Pydantic (never trust raw LLM output)
        try:
            data = json.loads(raw)
            q_create = QuestionCreate(
                topic=topic, subtopic=subtopic, difficulty=difficulty,
                type=type, **data
            )
        except (json.JSONDecodeError, ValidationError) as e:
            raise HTTPException(502, f'AI response invalid: {e}')

        # 5. Save to DB (ai_generated=True, reviewed=False)
        question = await self.q_repo.create(
            q_create, ai_generated=True, reviewed=False, db=db
        )

        # 6. Log to ai_gen_log for cost tracking
        await self.q_repo.log_ai_gen(
            question_id=question.id, user_id=user_id,
            prompt=prompt, raw_response=raw,
            tokens=tokens, cost=tokens * 0.00000015, db=db
        )
        return question
