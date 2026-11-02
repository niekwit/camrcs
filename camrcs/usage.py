"""camrcs usage: total size of uploaded archives"""

import logging
import os

import pandas as pd

from camrcs import data_csv
from camrcs.utils import convert_bytes, setup_logging


def usage():
    """Print how much data has been uploaded to RCS."""
    setup_logging()
    # open data.csv
    csv = pd.read_csv(os.path.join(data_csv.cdir, "data.csv"))

    # get size of each archive (ignore entries not yet uploaded)
    archive_size = csv["archive_size"].dropna()

    # convert any amount in MB in archive_size to bytes
    archive_size = archive_size.str.replace(" MB", "e6")

    # convert any amount in GB in archive_size to bytes
    archive_size = archive_size.str.replace(" GB", "e9")

    # convert any amount in TB in archive_size to bytes
    archive_size = archive_size.str.replace(" TB", "e12")

    # convert to float
    archive_size = archive_size.astype(float)

    # get total size of all archives
    total_size = sum(archive_size)

    logging.info(
        f"Total estimated size of all archives on RCS: {convert_bytes(total_size)}"
    )
