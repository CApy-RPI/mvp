from pydantic_settings import BaseSettings
from functools import lru_cache
import typing


class Settings(BaseSettings):
    # Bot settings
    BOT_TOKEN: str

    # MongoDB settings
    MONGO_URI: str
    MONGO_DBNAME: str
    MONGO_USERNAME: str
    MONGO_PASSWORD: str

    # Email settings
    MAILJET_API_KEY: typing.Optional[str] = ""
    MAILJET_API_SECRET: typing.Optional[str] = ""
    EMAIL_ADDRESS: typing.Optional[str] = ""

    # Channel settings
    WHO_DUNNIT: typing.Optional[str] = None
    DEV_LOCKED_CHANNEL_ID: typing.Optional[int] = None

    # Error handling settings
    FAILED_COMMANDS_INVITE_EXPIRY: typing.Optional[int] = 300
    FAILED_COMMANDS_INVITE_USES: typing.Optional[int] = 1
    FAILED_COMMANDS_GUILD_ID: int
    FAILED_COMMANDS_CHANNEL_ID: int
    FAILED_COMMANDS_ROLE_ID: int

    # Path settings
    COG_PATH: typing.Optional[str] = "frontend/cogs"
    MAJORS_PATH: typing.Optional[str] = "backend/res/majors.txt"

    # Chatbot settings
    ENABLE_CHATBOT: bool
    MODEL_NAME: str
    MESSAGE_LIMIT: typing.Optional[int] = 500

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()
