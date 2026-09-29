import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseModel):
    HINDSIGHT_URL: str = os.getenv("HINDSIGHT_URL", "http://localhost:8888")
    HINDSIGHT_BANK_ID: str = os.getenv("HINDSIGHT_BANK_ID", "team-payments")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "auto")  # 'gemini', 'openai', 'claude', 'auto'
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "incident_iq.db")
    AUTO_REFLECT_INTERVAL: int = int(os.getenv("AUTO_REFLECT_INTERVAL", "5"))
    ENVIRONMENT_NAME: str = "SIMULATED-FINTECH-PROD"

settings = Settings()
