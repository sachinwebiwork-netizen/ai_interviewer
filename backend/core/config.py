from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Interviewer Backend"
    PORT: int = 8000
    
    # Hugging Face Settings
    HF_TOKEN: str = ""
    
    # Postgres URL
    DATABASE_URL: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
