import os
import logging
from time import strftime, gmtime
import socket
import sys

def init_logger():
    if not os.path.exists("logs"):
        os.mkdir("logs")

    logging.basicConfig(filename=f'logs/{strftime("%Y-%m-%d %H:%M:%S", gmtime())}@{socket.gethostname()}.log',
                        level=logging.INFO)

    except_logger = logging.getLogger("sys")

    def handler(type, value, tb):
        except_logger.exception("Uncaught exception: {0}".format(str(value)), stack_info=True)

    sys.excepthook = handler
