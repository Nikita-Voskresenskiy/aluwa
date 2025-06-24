from pydantic_settings import BaseSettings
class EnvSettings(BaseSettings):
    BOT_TOKEN: str
    BOT_USERNAME: str
    BOT_ADMIN_ID: int
    DEBUG: bool = False
    DOMAIN_NAME: str
    JWT_SECRET_KEY: str
    COOKIE_NAME: str
    DB_DRIVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int
    POSTGRES_HOST: str

    @property
    def DATABASE_URL_asyncpg(self):
        return f"{self.DB_DRIVER}://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"

env = EnvSettings()