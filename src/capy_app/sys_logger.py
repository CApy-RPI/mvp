import logging
import os
import socket
import sys
from time import gmtime, strftime

WARNING = "\033[93m"
FAIL = "\033[91m"


def init_logger():
    if not os.path.exists("logs"):
        os.mkdir("logs")

    logfile = f'logs/{strftime("%Y-%m-%d_%H-%M-%S", gmtime())}@{socket.gethostname()}.log'
    logging.basicConfig(filename=logfile, level=logging.INFO)

    except_logger = logging.getLogger("sys")

    def handler(type, value, tb):
        print(f"{FAIL}ENCOUNTERED {type.__name__}: CHECK {logfile} FOR MORE DETAILS")
        except_logger.exception(f"Uncaught exception: {value!s}", stack_info=True)

    sys.excepthook = handler
