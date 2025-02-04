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
    bot.run(os.getenv("BOT_TOKEN"), reconnect=True)


if __name__ == "__main__":
    main()
