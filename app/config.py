from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv() # Load variables into os.environ for LangSmith

class Settings(BaseSettings):
    # Database
    DATABASE_URL:         str   # postgresql+asyncpg://user:pass@host/db

    # Redis
    REDIS_URL:            str   # redis://localhost:6379/0

    # Auth
    SECRET_KEY:           str
    ALGORITHM:            str = 'HS256'
    ACCESS_TOKEN_EXPIRE:  int = 60  # minutes

    # AI
    OPENAI_API_KEY:       str
    OPENAI_MODEL:         str = 'gpt-4o-mini'

    # LangSmith
    LANGSMITH_TRACING:    str | None = None
    LANGSMITH_ENDPOINT:   str | None = None
    LANGSMITH_API_KEY:    str | None = None
    LANGSMITH_PROJECT:    str | None = None

    # Score thresholds
    PASS_THRESHOLD_PCT:   int = 60
    ADVANCE_THRESHOLD_PCT:int = 80
    DROP_THRESHOLD_PCT:   int = 50
    ADAPTIVE_WINDOW_Q:    int = 5   # questions before re-evaluating difficulty

    class Config:
        env_file = '.env'

settings = Settings()
