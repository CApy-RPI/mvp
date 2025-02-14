# stl imports
import os

from capy_app.sys_logger import init_logger
# local imports
from frontend.bot import Bot

# Set the current working directory to the location of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    init_logger()
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    main()
