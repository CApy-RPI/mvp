from pydantic_settings import BaseSettings
from functools import lru_cache
import typing


class Settings(BaseSettings):
    # Bot settings
    BOT_TOKEN: typing.Optional[str] = None

    # MongoDB settings
    MONGO_URI: typing.Optional[str] = None
    MONGO_DBNAME: typing.Optional[str] = None
    MONGO_USERNAME: typing.Optional[str] = None
    MONGO_PASSWORD: typing.Optional[str] = None

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
    FAILED_COMMANDS_GUILD_ID: typing.Optional[int] = None
    FAILED_COMMANDS_CHANNEL_ID: typing.Optional[int] = None
    FAILED_COMMANDS_ROLE_ID: typing.Optional[int] = None

    # Path settings
    COG_PATH: typing.Optional[str] = "frontend/cogs"
    MAJORS_PATH: typing.Optional[str] = "backend/res/majors.txt"

    # Chatbot settings
    ENABLE_CHATBOT: typing.Optional[bool] = None
    MODEL_NAME: typing.Optional[str] = None
    MESSAGE_LIMIT: typing.Optional[int] = 500

    # Debug guild setting
    DEBUG_GUILD_ID: typing.Optional[int] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()
