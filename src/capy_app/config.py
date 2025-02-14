from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
from pydantic import field_validator


class Settings(BaseSettings):
    # Logging settings
    LOG_LEVEL: Optional[str] = "DEBUG"

    # Bot settings
    BOT_TOKEN: Optional[str] = None
    BOT_COMMAND_PREFIX: Optional[str] = "!"

    # MongoDB settings
    MONGO_URI: Optional[str] = None
    MONGO_DBNAME: Optional[str] = None
    MONGO_USERNAME: Optional[str] = None
    MONGO_PASSWORD: Optional[str] = None

    # Email settings
    MAILJET_API_KEY: Optional[str] = ""
    MAILJET_API_SECRET: Optional[str] = ""
    MAILJET_API_EMAIL: Optional[str] = ""

    # Channel settings
    WHO_DUNNIT: Optional[str] = None
    DEV_LOCKED_CHANNEL_ID: Optional[int] = None

    # Developer channels
    TICKET_BUG_REPORT_CHANNEL_ID: Optional[int] = None
    TICKET_FEEDBACK_CHANNEL_ID: Optional[int] = None
    TICKET_FEATURE_REQUEST_CHANNEL_ID: Optional[int] = None

    # Error handling settings
    FAILED_COMMANDS_INVITE_EXPIRY: Optional[int] = 300
    FAILED_COMMANDS_INVITE_USES: Optional[int] = 1
    FAILED_COMMANDS_GUILD_ID: Optional[int] = None
    FAILED_COMMANDS_CHANNEL_ID: Optional[int] = None
    FAILED_COMMANDS_ROLE_ID: Optional[int] = None

    # Path settings
    COG_PATH: Optional[str] = "frontend/cogs"
    MAJORS_PATH: Optional[str] = "frontend/resources/majors.txt"

    # Chatbot settings
    ENABLE_CHATBOT: Optional[bool] = None
    MODEL_NAME: Optional[str] = None
    MESSAGE_LIMIT: Optional[int] = 500

    # Debug guild setting
    DEBUG_GUILD_ID: Optional[int] = None

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }

    # Validators
    @field_validator("MONGO_URI")
    def validate_mongo_uri(cls, v):
        if (
            v is not None
            and not v.startswith("mongodb://")
            and not v.startswith("mongodb+srv://")
        ):
            raise ValueError(
                'MONGO_URI must start with "mongodb://" or "mongodb+srv://"'
            )
        return v

    @field_validator("MAILJET_API_EMAIL")
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError("MAILJET_API_EMAIL must be a valid email address")
        return v

    @field_validator(
        "FAILED_COMMANDS_INVITE_EXPIRY", "FAILED_COMMANDS_INVITE_USES", "MESSAGE_LIMIT"
    )
    def validate_positive_numbers(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Value must be a positive integer")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()
