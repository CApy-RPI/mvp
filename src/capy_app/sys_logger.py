import os
import logging
from time import strftime, gmtime
import socket
import sys

WARNING = "\033[93m"
FAIL = "\033[91m"


def init_logger():
    if not os.path.exists("logs"):
        os.mkdir("logs")

    logfile = f'logs/{strftime("%Y-%m-%d %H:%M:%S", gmtime())}@{socket.gethostname()}.log'
    logging.basicConfig(filename=logfile,
                        level=logging.INFO)

    except_logger = logging.getLogger("sys")

    def handler(type, value, tb):
        print(f'{FAIL}ENCOUNTERED {type.__name__}: CHECK {logfile} FOR MORE DETAILS')
        except_logger.exception("Uncaught exception: {0}".format(str(value)), stack_info=True)

    sys.excepthook = handler
