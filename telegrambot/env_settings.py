from pydantic_settings import BaseSettings
class EnvSettings(BaseSettings):
    BOT_TOKEN: str
    BOT_ADMIN_ID: int
    DEBUG: bool = False
    DOMAIN_NAME: str
    JWT_SECRET_KEY: str
    COOKIE_NAME: str

    class Config:
        env_file = ".env"