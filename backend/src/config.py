"""Configuration settings."""
from pydantic_settings import BaseSettings
from typing import Optional
from pydantic import Field


class Settings(BaseSettings):
    """Application settings - reads from environment variables.
    
    All values are read from environment variables. Defaults shown are only
    used if the environment variable is not set.
    """
    
    # Database - reads from DATABASE_URL environment variable
    # In Docker: postgresql+asyncpg://postgres:postgres@postgres:5432/hospital_ai_assistant
    # Local dev: postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_ai_assistant
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/hospital_ai_assistant",
        description="Database connection URL"
    )
    
    # OpenAI - reads from OPENAI_API_KEY environment variable
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    openai_temperature: float = Field(default=0.7, description="OpenAI temperature")
    openai_max_tokens: int = Field(default=2000, description="OpenAI max tokens")
    
    # JWT - reads from JWT_SECRET_KEY environment variable
    jwt_secret_key: str = Field(default="", description="JWT secret key")
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration_hours: int = Field(default=24, description="JWT expiration hours")
    
    # Server
    backend_port: int = Field(default=8000, description="Backend port")
    frontend_port: int = Field(default=3000, description="Frontend port")
    
    # CORS
    cors_origins: str = Field(default="http://localhost:3000", description="CORS allowed origins")
    
    # Doctor Recommendation
    top_doctors_count: int = Field(default=5, description="Number of top doctors to recommend")
    
    # LangSmith (for observability and tracing)
    langsmith_api_key: Optional[str] = Field(default=None, description="LangSmith API key")
    langsmith_tracing: bool = Field(default=False, description="Enable LangSmith tracing")
    langsmith_project: Optional[str] = Field(default="hospital-ai-assistant", description="LangSmith project name")
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
    }


settings = Settings()
