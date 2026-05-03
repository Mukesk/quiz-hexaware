import redis.asyncio as redis
from typing import AsyncGenerator
from app.config import settings

redis_pool = redis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True
)

async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    client = redis.Redis.from_pool(redis_pool)
    try:
        yield client
    finally:
        await client.close()
