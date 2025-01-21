import os
import discord
import logging
from discord.ext import commands
from dotenv import load_dotenv
from modules.database import Database
from modules.email_auth import create_app
import threading


def run_flask():
    app = create_app()
    app.run(port=5000)


def main():
    load_dotenv()
    bot = Bot(command_prefix="!", intents=discord.Intents.all())

    """
    DEVS: If testing bot in certain channel to avoid conflicts with other bot instances set CHANNEL_LOCK = "True" in .env
    otherwise can remove CHANNEL_LCOK or set CHANNEL_LOCK = "False"
    """
    # Set the allowed channel ID and channel lock from environment
    allowed_channel_id = os.getenv("ALLOWED_CHANNEL_ID")
    channel_lock_str = os.getenv("CHANNEL_LOCK") or "False"
    channel_lock = channel_lock_str == "TRUE"
    if allowed_channel_id and channel_lock:
        bot.allowed_channel_id = int(allowed_channel_id)
    else:
        bot.allowed_channel_id = None

    bot.run(os.getenv("DEV_BOT_TOKEN"), reconnect=True)


if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    main()
