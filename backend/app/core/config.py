from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FIP - Financial, Inventory and Payroll System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = "development"

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "fip_user"
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str = "fip_db"
    POSTGRES_PORT: str = "5432"

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8

    CORS_ORIGINS: list[str] = []

    @field_validator("ENVIRONMENT")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"development", "test", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {sorted(allowed)}")
        return value

    def model_post_init(self, __context: object) -> None:
        if len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must contain at least 32 characters")
        if self.ENVIRONMENT == "production" and self.ACCESS_TOKEN_EXPIRE_MINUTES > 24 * 60:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES cannot exceed 24 hours in production")

    @property
    def async_database_uri(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
