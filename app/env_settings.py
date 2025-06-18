from pydantic_settings import BaseSettings
class EnvSettings(BaseSettings):
    BOT_TOKEN: str
    BOT_ADMIN_ID: int
    DEBUG: bool = False
    JWT_SECRET_KEY: str
    COOKIE_NAME: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int
    POSTGRES_HOST: str
    PGDATA: str

    class Config:
        env_file = ".env"