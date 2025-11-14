from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Logging settings
    LOG_LEVEL: str | None = "DEBUG"
    STAT_DUMP_FREQUENCY: float | None = 10  # Minutes

    # The computed path to the statistics log file. Only mutated at definition.
    STAT_LOG_FILE: Path | None = None

    # Bot settings
    BOT_TOKEN: str | None = None
    BOT_COMMAND_PREFIX: str | None = "!"

    # MongoDB settings
    MONGO_URI: str | None = None
    MONGO_DBNAME: str | None = None
    MONGO_USERNAME: str | None = None
    MONGO_PASSWORD: str | None = None

    # Email settings
    MAILJET_API_KEY: str | None = ""
    MAILJET_API_SECRET: str | None = ""
    MAILJET_API_EMAIL: str | None = ""

    # Channel settings
    WHO_DUNNIT: str | None = None
    DEV_LOCKED_CHANNEL_ID: int | None = None

    # Developer channels
    TICKET_BUG_REPORT_CHANNEL_ID: int | None = None
    TICKET_FEEDBACK_CHANNEL_ID: int | None = None
    TICKET_FEATURE_REQUEST_CHANNEL_ID: int | None = None

    # Error handling settings
    FAILED_COMMANDS_INVITE_EXPIRY: int | None = 300
    FAILED_COMMANDS_INVITE_USES: int | None = 1
    FAILED_COMMANDS_GUILD_ID: int | None = None
    FAILED_COMMANDS_CHANNEL_ID: int | None = None
    FAILED_COMMANDS_ROLE_ID: int | None = None

    # Path settings
    COG_PATH: str | None = "frontend/cogs"
    MAJORS_PATH: str | None = "frontend/resources/majors.txt"

    # Chatbot settings
    ENABLE_CHATBOT: bool | None = None
    MODEL_NAME: str | None = None
    MESSAGE_LIMIT: int | None = 500

    # Debug guild setting
    DEBUG_GUILD_ID: int | None = None

    # Onboarding settings
    ONBOARDING_ENABLED: bool | None = True
    ONBOARDING_MODE: str | None = "announce"  # announce | dm | silent
    ONBOARDING_REQUIRE_MANAGE_GUILD: bool | None = True
    ONBOARDING_FALLBACK_CHANNEL_ID: int | None = None
    ONBOARDING_DOCS_URL: str | None = None
    ONBOARDING_MESSAGE: str | None = "Thanks for adding me! Admins can configure channels/roles and features."

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }

    # Validators

    # @field_validator("MONGO_URI")
    # def validate_mongo_uri(cls, v):
    #     """Check if Mongo URI is a valid URI"""
    #     if (
    #         v is not None
    #         and not v.startswith("mongodb://")
    #         and not v.startswith("mongodb+srv://")
    #     ):
    #         raise ValueError(
    #             'MONGO_URI must start with "mongodb://" or "mongodb+srv://"'
    #         )
    #     return v
    #
    # @field_validator("MAILJET_API_EMAIL")
    # def validate_email(cls, v):
    #
    #     # Regex for Email Validation
    #     regex = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
    #     """Check if the MailJet API email is a valid email"""
    #     if not (re.fullmatch(regex, v)):
    #         raise ValueError("MAILJET_API_EMAIL must be a valid email address")
    #     return v
    #
    # @field_validator("MONGO_DBNAME")
    # def validate_mongo_dbname(cls, v):
    #     """Check if the Mongo DB name is a valid database name"""
    #     if v is not None and " " in v:
    #         raise ValueError("MONGO_DBNAME must not contain spaces.")
    #     return v
    #
    # @field_validator("ENABLE_CHATBOT")
    # def validate_enable_chatbot(cls, v):
    #     """Check if enable_chatbot variable is a boolean value"""
    #     if v is not True and v is not False:
    #         raise ValueError("ENABLE_CHATBOT must be 'True' or 'False'")
    #     return v
    #
    # @field_validator(
    #     "BOT_TOKEN",
    #     "MONGO_URI",
    #     "MONGO_DBNAME",
    #     "MONGO_USERNAME",
    #     "MONGO_PASSWORD",
    #     "MAILJET_API_KEY",
    #     "MAILJET_API_SECRET",
    #     "MAILJET_API_EMAIL",
    #     "TICKET_BUG_REPORT_CHANNEL_ID",
    #     "TICKET_FEATURE_REQUEST_CHANNEL_ID",
    #     "TICKET_FEEDBACK_CHANNEL_ID",
    #     "WHO_DUNNIT",
    #     "FAILED_COMMANDS_GUILD_ID",
    #     "FAILED_COMMANDS_CHANNEL_ID",
    #     "FAILED_COMMANDS_ROLE_ID",
    #     "ENABLE_CHATBOT",
    #     "MODEL_NAME",
    #     "DEBUG_GUILD_ID",
    # )
    # def validate_fields(cls, v, info):
    #     """Check if any of the env variables are empty/missing"""
    #     if v is None or v == "":
    #         raise ValueError(f"Field '{info.field_name}' is empty.")
    #     return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()
