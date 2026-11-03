"""Reading and updating data.csv"""

import logging
import os
import shutil

import pandas as pd

# Columns that identify what was transferred for an entry
IDENTITY_COLUMNS = ["project_dir", "target_dir", "remote_dest_dir"]

STRING_COLUMNS = [
    "date_up",
    "date_down",
    "md5sum_up",
    "md5sum_down",
    "archive_size",
    "version",
]

# Get current working dir
cdir = os.getcwd()


def read_csv():
    """Reads data.csv"""
    # columns written to by camrcs must be strings: empty columns would otherwise
    # be read as floats, which pandas>=3 does not allow strings to be written to
    csv = pd.read_csv(
        os.path.join(cdir, "data.csv"),
        dtype={column: str for column in STRING_COLUMNS},
    )

    return csv.set_index("id")


def update_csv(entry, row, **values):
    """Updates one entry in data.csv, unless row (read before the transfer) no longer matches it"""
    logging.info("Updating data.csv...")
    csv_file = os.path.join(cdir, "data.csv")
    temp_file = f"{csv_file}.tmp"

    # read again to keep any changes made since the start of the run
    csv = read_csv()

    # do not record the transfer in an entry that was deleted or changed during it
    if entry not in csv.index or any(
        csv.at[entry, column] != row[column] for column in IDENTITY_COLUMNS
    ):
        logging.error(
            f"Entry {entry} was deleted or changed during the transfer, so data.csv was not updated!"
        )
        logging.error(f"Transfer of {row['target_dir']}: {values}")
        return False

    for column, value in values.items():
        csv.loc[entry, column] = value

    shutil.copy2(csv_file, f"{csv_file}.bak")
    with open(temp_file, "w") as f:
        csv.to_csv(f)
        f.flush()
        os.fsync(f.fileno())

    # atomic: data.csv is always the complete old or new version
    os.replace(temp_file, csv_file)

    return True


def test_csv():
    assert os.path.exists(os.path.join(cdir, "data.csv")) == True, "data.csv not found!"
