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
    POSTGRES_CONFIG_TCP_KEEPALIVES_IDLE: int
    POSTGRES_CONFIG_TCP_KEEPALIVES_INTERVAL: int
    POSTGRES_CONFIG_TCP_KEEPALIVES_COUNT: int
    SSH_HOST: str
    SSH_PORT: int
    SSH_USERNAME: str
    SSH_PRIVATE_KEY_PATH: str
    LOCAL: bool = False

    class Config:
        env_file = ".env"