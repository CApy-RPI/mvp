import logging
import socket
import sys
from pathlib import Path
from time import gmtime, strftime

import config

WARNING = "\033[93m"
FAIL = "\033[91m"

LOGS_DIR = Path(__file__).parents[2].joinpath("logs")
_STAT_FILE = (
    Path(__file__).parents[2].joinpath("stats")
)  # Initially just make it the directory - this changes p much immediately


def init_logger():
    # Use pathlib.Path instead of os.path / os.mkdir
    if not LOGS_DIR.exists():
        LOGS_DIR.mkdir(parents=True)
    formatted_time = strftime("%Y-%m-%d_%H-%M-%S", gmtime())
    logfile = LOGS_DIR / f"{formatted_time}@{socket.gethostname()}.log"

    # Initialize logging to that file
    logging.basicConfig(filename=str(logfile), level=logging.INFO)

    except_logger = logging.getLogger("sys")

    def handler(exc_type, exc_value, _exc_tb):
        sys.stderr.write(f"{FAIL}ENCOUNTERED {exc_type.__name__}: CHECK {logfile} FOR MORE DETAILS\n")
        except_logger.exception(f"Uncaught exception: {exc_value!s}", stack_info=True)

    sys.excepthook = handler

    # Create stats directory if it doesn't exist
    if not _STAT_FILE.exists():
        _STAT_FILE.mkdir(parents=True)

    # Assign global stat filepath
    config.settings.STAT_LOG_FILE = _STAT_FILE.joinpath(f"{formatted_time}@{socket.gethostname()}.stat.log")
