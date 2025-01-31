import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
DEV_BOT_TOKEN: str = os.getenv("DEV_BOT_TOKEN", "")

MONGO_URI: str = os.getenv("MONGO_URI", "")
MONGO_DBNAME: str = os.getenv("MONGO_DBNAME", "")
MONGO_USERNAME: str = os.getenv("MONGO_USERNAME", "")
MONGO_PASSWORD: str = os.getenv("MONGO_PASSWORD", "")

MAILJET_API_KEY: str = os.getenv("MAILJET_API_KEY", "")
MAILJET_API_SECRET: str = os.getenv("MAILJET_API_SECRET", "")
EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")

ALLOWED_CHANNEL_ID = os.getenv("ALLOWED_CHANNEL_ID")
CHANNEL_LOCK = os.getenv("CHANNEL_LOCK")

COG_PATH = "frontend/cogs"
MAJORS_PATH = "backend/res/majors.txt"

ENABLE_CHATBOT = bool(os.getenv("ENABLE_CHATBOT", False))
