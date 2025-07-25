# stl imports
import os
from pathlib import Path

# local imports
from frontend.bot import Bot
from sys_logger import init_logger

# Set the current working directory to the location of this file
os.chdir(Path(__file__).resolve().parent)


def main():
    init_logger()
    bot = Bot()
    bot.run_bot()


if __name__ == "__main__":
    main()
