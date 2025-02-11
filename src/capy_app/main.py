# stl imports
import os
import logging
from time import strftime, gmtime
import socket

# local imports
from frontend.bot import Bot

# Set the current working directory to the location of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def main():
    if not os.path.exists("logs"):
        os.mkdir("logs")

    logging.basicConfig(filename = f'logs/{strftime("%Y-%m-%d %H:%M:%S", gmtime())}@{socket.gethostname()}.log',level=logging.INFO)

    bot = Bot()
    bot.run()


if __name__ == "__main__":
    main()
