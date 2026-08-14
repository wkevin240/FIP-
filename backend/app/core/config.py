from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "FIP - Financial, Inventory and Payroll System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: str = "fip_user"
    POSTGRES_PASSWORD: str = "fip_password"
    POSTGRES_DB: str = "fip_db"
    POSTGRES_PORT: str = "5432"
    POSTGRES_MIGRATION_USER: str | None = None
    POSTGRES_MIGRATION_PASSWORD: str | None = None

    # Accounting database authorization
    ACCOUNTING_POSTING_TOKEN: str | None = None

    # Security
    SECRET_KEY: str = "super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    CORS_ORIGINS: list[str] = []

    @property
    def async_database_uri(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def async_migration_database_uri(self) -> str:
        migration_user = self.POSTGRES_MIGRATION_USER or self.POSTGRES_USER
        migration_password = self.POSTGRES_MIGRATION_PASSWORD or self.POSTGRES_PASSWORD
        return f"postgresql+asyncpg://{migration_user}:{migration_password}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


settings = Settings()
