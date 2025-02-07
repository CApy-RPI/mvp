from pydantic_settings import BaseSettings
from pydantic import validator, Field
from functools import lru_cache
import typing


class Settings(BaseSettings):
    """
    Configuration settings for the application.

    Settings are loaded from environment variables or a `.env` file.
    """

    # Bot settings
    BOT_TOKEN: typing.Optional[str] = Field(None, description="Bot token for authentication with API services.")

    # MongoDB settings
    MONGO_URI: typing.Optional[str] = Field(None, description="MongoDB connection URI.")
    MONGO_DBNAME: typing.Optional[str] = Field(None, description="Name of the MongoDB database.")
    MONGO_USERNAME: typing.Optional[str] = Field(None, description="Username for MongoDB authentication.")
    MONGO_PASSWORD: typing.Optional[str] = Field(None, description="Password for MongoDB authentication.")

    # Email settings
    MAILJET_API_KEY: typing.Optional[str] = Field("", description="API key for Mailjet service.")
    MAILJET_API_SECRET: typing.Optional[str] = Field("", description="API secret for Mailjet service.")
    EMAIL_ADDRESS: typing.Optional[str] = Field("", description="Email address for sending notifications.")

    # Channel settings
    WHO_DUNNIT: typing.Optional[str] = Field(None, description="Identifier for the 'Who Dunnit' channel.")
    DEV_LOCKED_CHANNEL_ID: typing.Optional[int] = Field(None, description="Channel ID for the development locked channel.")

    # Error handling settings
    FAILED_COMMANDS_INVITE_EXPIRY: typing.Optional[int] = Field(300, description="Expiry time in seconds for failed command invites.")
    FAILED_COMMANDS_INVITE_USES: typing.Optional[int] = Field(1, description="Number of uses allowed for failed command invites.")
    FAILED_COMMANDS_GUILD_ID: typing.Optional[int] = Field(None, description="Guild ID for handling failed commands.")
    FAILED_COMMANDS_CHANNEL_ID: typing.Optional[int] = Field(None, description="Channel ID for failed command reports.")
    FAILED_COMMANDS_ROLE_ID: typing.Optional[int] = Field(None, description="Role ID for users handling failed commands.")

    # Path settings
    COG_PATH: typing.Optional[str] = Field("frontend/cogs", description="Path to the bot's cog files.")
    MAJORS_PATH: typing.Optional[str] = Field("backend/res/majors.txt", description="Path to the majors data file.")

    # Chatbot settings
    ENABLE_CHATBOT: typing.Optional[bool] = Field(None, description="Enable or disable the chatbot feature.")
    MODEL_NAME: typing.Optional[str] = Field(None, description="Name of the AI model used for the chatbot.")
    MESSAGE_LIMIT: typing.Optional[int] = Field(500, description="Maximum number of messages the chatbot can process.")

    class Config:
        env_file = ".env"
        case_sensitive = True

    # Validators
    @validator('BOT_TOKEN')
    def validate_bot_token(cls, v):
        if v is not None and not v.startswith('Bot '):
            raise ValueError('BOT_TOKEN must start with "Bot "')
        return v

    @validator('MONGO_URI')
    def validate_mongo_uri(cls, v):
        if v is not None and not v.startswith('mongodb://') and not v.startswith('mongodb+srv://'):
            raise ValueError('MONGO_URI must start with "mongodb://" or "mongodb+srv://"')
        return v

    @validator('EMAIL_ADDRESS')
    def validate_email(cls, v):
        if v and "@" not in v:
            raise ValueError('EMAIL_ADDRESS must be a valid email address')
        return v

    @validator('FAILED_COMMANDS_INVITE_EXPIRY', 'FAILED_COMMANDS_INVITE_USES', 'MESSAGE_LIMIT')
    def validate_positive_numbers(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Value must be a positive integer')
        return v


@lru_cache()
def get_settings() -> Settings:
    """
    Get a cached instance of the Settings object.

    This ensures settings are only loaded and validated once.
    """
    return Settings()


# Create a global settings instance
settings = get_settings()
