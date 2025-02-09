# stl imports
import os

# local imports
from frontend.bot import Bot

# Set the current working directory to the location of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    bot = Bot()
    bot.run()


if __name__ == "__main__":
    main()
