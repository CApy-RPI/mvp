import logging
import socket
import sys
from pathlib import Path
from time import gmtime, strftime

WARNING = "\033[93m"
FAIL = "\033[91m"


def init_logger():
    # Use pathlib.Path instead of os.path / os.mkdir
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir(parents=True)
    logfile = logs_dir / f"{strftime('%Y-%m-%d_%H-%M-%S', gmtime())}@{socket.gethostname()}.log"

    # Initialize logging to that file
    logging.basicConfig(filename=str(logfile), level=logging.INFO)

    except_logger = logging.getLogger("sys")

    def handler(exc_type, exc_value, _exc_tb):
        sys.stderr.write(f"{FAIL}ENCOUNTERED {exc_type.__name__}: CHECK {logfile} FOR MORE DETAILS\n")
        except_logger.exception(f"Uncaught exception: {exc_value!s}", stack_info=True)

    sys.excepthook = handler
