"""Configuration settings."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings."""
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/hospital_ai_assistant"
    
    # OpenAI
    openai_api_key: str = "your_openai_api_key"
    openai_model: str = "gpt-4o-mini"
    openai_temperature: float = 0.7
    openai_max_tokens: int = 2000
    
    # JWT
    jwt_secret_key: str = "your_secret_key_change_this_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24
    
    # Server
    backend_port: int = 8000
    frontend_port: int = 3000
    
    # CORS
    cors_origins: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
