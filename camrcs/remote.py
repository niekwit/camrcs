"""Storage services (RCS and RDV) and remote paths"""

import logging
import subprocess
import sys


def remote_host(project_dir):
    """Returns login address of the storage service that holds project_dir"""
    if project_dir.startswith("/rdv"):
        return "rdv.uis.cam.ac.uk"
    elif project_dir.startswith("/rcs"):
        return "rcs.uis.cam.ac.uk"

    logging.error(f"project_dir ({project_dir}) should start with /rcs or /rdv!")
    sys.exit(1)


def remote_path_is_file(remote_path):
    """Checks if a remote path is a regular file (requires a separate RCS login)"""
    logging.info(f"Checking if {remote_path} is a file...")
    result = subprocess.run(
        f"rsync --list-only {remote_path}",
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )
    if result.returncode != 0:
        logging.error(f"Could not list {remote_path}")
        sys.exit(1)

    # last line, as any login message is printed before the listing
    return result.stdout.strip().splitlines()[-1].startswith("-")
