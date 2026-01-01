from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    
    # Application
    APP_NAME: str = "Gas Agency Management"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    
    @property
    def origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

settings = Settings()