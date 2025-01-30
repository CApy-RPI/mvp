# stl imports
import os
from dotenv import load_dotenv

# third party imports
import discord

# local imports
from frontend.bot import Bot
from config import ALLOWED_CHANNEL_ID, CHANNEL_LOCK

# Set the current working directory to the location of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    load_dotenv()
    bot = Bot(command_prefix="!", intents=discord.Intents.all())
    """
    DEVS: If testing bot in certain channel to avoid conflicts with other bot instances set CHANNEL_LOCK = "True" in .env
    otherwise can remove CHANNEL_LOCK or set CHANNEL_LOCK = "False"
    """
    # Set the allowed channel ID and channel lock from environment
    channel_lock_str = CHANNEL_LOCK or "False"
    channel_lock = channel_lock_str == "TRUE"
    if ALLOWED_CHANNEL_ID and channel_lock:
        bot.allowed_channel_id = int(ALLOWED_CHANNEL_ID)
    else:
        bot.allowed_channel_id = None
    bot.run(os.getenv("DEV_BOT_TOKEN"), reconnect=True)


if __name__ == "__main__":
    main()
