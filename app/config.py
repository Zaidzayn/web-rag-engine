# app/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='../.env', env_file_encoding='utf-8', extra='ignore')

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int

    QDRANT_HOST: str
    QDRANT_PORT: int
    
    # Updated for Groq and local embeddings
    GROQ_API_KEY: str
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    GENERATIVE_MODEL_NAME: str = "openai/gpt-oss-20b"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

settings = Settings()