from pydantic_settings import BaseSettings
from pydantic import Field
import typing
import warnings
from functools import lru_cache


class Settings(BaseSettings):
    # Bot settings
    BOT_TOKEN: str

    # MongoDB settings
    MONGO_URI: str
    MONGO_DBNAME: str
    MONGO_USERNAME: str
    MONGO_PASSWORD: str

    # Email settings
    MAILJET_API_KEY: str = ""
    MAILJET_API_SECRET: str = ""
    EMAIL_ADDRESS: str = ""

    # Channel settings
    WHO_DUNNIT: typing.Optional[str] = None
    DEV_LOCKED_CHANNEL_ID: typing.Optional[int] = None

    # Error handling settings
    FAILED_COMMANDS_INVITE_EXPIRY: int = 48
    FAILED_COMMANDS_INVITE_USES: int = 1
    FAILED_COMMANDS_GUILD_ID: typing.Optional[int] = None
    FAILED_COMMANDS_CHANNEL_ID: typing.Optional[int] = None

    # Path settings
    COG_PATH: str = "frontend/cogs"
    MAJORS_PATH: str = "backend/res/majors.txt"

    # Chatbot settings
    ENABLE_CHATBOT: bool = Field(default=False, validate_default=True)
    MODEL_NAME: str = ""
    MESSAGE_LIMIT: int = 500

    class Config:
        env_file = ".env"
        case_sensitive = True

        @classmethod
        def parse_env_var(
            cls, field_name: str, raw_val: str
        ) -> typing.Union[str, bool, int]:
            if field_name in ["CHANNEL_LOCK", "ENABLE_CHATBOT"]:
                return raw_val.lower() in ("true", "t", "1", "yes", "y")
            return raw_val


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Create a global settings instance
settings = get_settings()


def _warn_deprecated(name: str, expected_type: type):
    warnings.warn(
        f"Accessing {name} directly is deprecated. Use get_settings().{name} instead. "
        f"Expected type: {expected_type.__name__}",
        DeprecationWarning,
        stacklevel=2,
    )


# For backwards compatibility, expose all settings as global variables with warnings
def __getattr__(name):
    if hasattr(settings, name):
        value = getattr(settings, name)
        expected_type = settings.__annotations__.get(name, type(value))
        _warn_deprecated(name, expected_type)
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


# Define all global variables to maintain static analysis compatibility

# Bot settings
BOT_TOKEN = str(settings.BOT_TOKEN)
DEV_BOT_TOKEN = str(settings.BOT_TOKEN or "")

# MongoDB settings
MONGO_URI = str(settings.MONGO_URI)
MONGO_DBNAME = str(settings.MONGO_DBNAME)
MONGO_USERNAME = str(settings.MONGO_USERNAME)
MONGO_PASSWORD = str(settings.MONGO_PASSWORD)

# Email settings
MAILJET_API_KEY = str(settings.MAILJET_API_KEY or "")
MAILJET_API_SECRET = str(settings.MAILJET_API_SECRET or "")
EMAIL_ADDRESS = str(settings.EMAIL_ADDRESS or "")

# Channel settings
ALLOWED_CHANNEL_ID = (
    int(settings.DEV_LOCKED_CHANNEL_ID) if settings.DEV_LOCKED_CHANNEL_ID else 0
)

# Path settings
COG_PATH = str(settings.COG_PATH)
MAJORS_PATH = str(settings.MAJORS_PATH)

# Chatbot settings
ENABLE_CHATBOT = bool(settings.ENABLE_CHATBOT)
MODEL_NAME = str(settings.MODEL_NAME or "")
MESSAGE_LIMIT = int(settings.MESSAGE_LIMIT)
