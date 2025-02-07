# stl imports
import os

# third party imports
import discord

# local imports
from frontend.bot import Bot
from config import settings

# Set the current working directory to the location of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    bot = Bot(command_prefix="!", intents=discord.Intents.all())
    bot.run(os.getenv(settings.BOT_TOKEN), reconnect=True)


if __name__ == "__main__":
    main()
