from pydantic_settings import BaseSettings, SettingsConfigDict
import urllib.parse

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
        encoded_pass = urllib.parse.quote(self.DB_PASS, safe="")
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{encoded_pass}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def WEBHOOK_URL_PATH(self):
        return f"{self.WEBHOOK_URL}{self.WEBHOOK_PATH}"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()