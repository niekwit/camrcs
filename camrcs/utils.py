"""Helpers shared by the commands: logging, shell commands and formatting"""

from datetime import datetime
import logging
import subprocess
import sys
import time
import timeit


def setup_logging():
    date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    log = f"camrcs_{date_time}.log"
    logging.basicConfig(
        format="%(levelname)s:%(asctime)s: %(message)s",
        level=logging.DEBUG,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(log), logging.StreamHandler()],
    )


def run(command, message=None):
    """Runs shell commands with exception handling"""
    if message:
        logging.info(message)

    try:
        command = subprocess.run(
            command,
            shell=True,
            executable="/bin/bash",  # process substitution does not work in all shells
            check=True,
        )
        if command.returncode == 0:
            logging.info("Done...")

            return True
        else:
            logging.error(command.stdout)

    except subprocess.CalledProcessError as error:
        logging.error(error)
        sys.exit(1)


def total_run_time(start):
    """Print total run time"""
    stop = timeit.default_timer()
    total_time = stop - start

    # Format time
    ty_res = time.gmtime(total_time)
    res = time.strftime("%H:%M:%S", ty_res)

    logging.info(f"Total run time: {res}")


def convert_bytes(num):
    """Converts bytes to MB.... GB... etc
    adapted from https://stackoverflow.com/questions/2104080/how-do-i-check-file-size-in-python#2104083
    """
    for x in ["bytes", "KB", "MB", "GB", "TB"]:
        if num < 1000.0:
            return f"{num:.1f} {x}"
        num /= 1000.0
