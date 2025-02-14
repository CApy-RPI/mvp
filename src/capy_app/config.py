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
        """Check if Mongo URI is a valid URI"""
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
        """Check if the MailJet API email is a valid email"""
        if v and "@" not in v:
            raise ValueError("MAILJET_API_EMAIL must be a valid email address")
        return v

    @field_validator("MONGO_DBNAME")
    def validate_mongo_dbname(cls, v):
        """Check if the Mongo DB name is a valid database name"""
        if " " in v:
            raise ValueError("MONGO_DBNAME must not contain spaces.")
        return v

    @field_validator("ENABLE_CHATBOT")
    def validate_enable_chatbot(cls, v):
        """Check if enable_chatbot variable is a boolean value"""
        if v is not True and v is not False:
            raise ValueError("ENABLE_CHATBOT must be 'True' or 'False'")
        return v

    @field_validator(
        "BOT_TOKEN",
        "MONGO_URI",
        "MONGO_DBNAME",
        "MONGO_USERNAME",
        "MONGO_PASSWORD",
        "MAILJET_API_KEY",
        "MAILJET_API_SECRET",
        "MAILJET_API_EMAIL",
        "TICKET_BUG_REPORT_CHANNEL_ID",
        "TICKET_FEATURE_REQUEST_CHANNEL_ID",
        "TICKET_FEEDBACK_CHANNEL_ID",
        "WHO_DUNNIT",
        "FAILED_COMMANDS_GUILD_ID",
        "FAILED_COMMANDS_CHANNEL_ID",
        "FAILED_COMMANDS_ROLE_ID",
        "ENABLE_CHATBOT",
        "MODEL_NAME",
        "DEBUG_GUILD_ID",
    )
    def validate_fields(cls, v, info):
        """Check if any of the env variables are empty/missing"""
        if v is None or v == "":
            raise ValueError(f"Field '{info.field_name}' is empty.")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()
