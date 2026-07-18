from pydantic_settings import BaseSettings, SettingsConfigDict

from src.telegram_bot.bot import WEBHOOK_URL, WEBHOOK_PATH


class Settings(BaseSettings):
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    WEBHOOK_PATH: str
    WEBHOOK_URL: str

    TELEGRAM_BOT_TOKEN: str

    @property
    def DB_URL(self):
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def WEBHOOK_URL_PATH(self):
        return f"{WEBHOOK_URL}{WEBHOOK_PATH}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()