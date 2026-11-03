"""camrcs down: retrieve and unpack an archive"""

from datetime import datetime
import logging
import os
import sys
import timeit

from camrcs.checksums import md5
from camrcs.data_csv import read_csv, update_csv
from camrcs.remote import remote_host, remote_path_is_file
from camrcs.single_part_bug import has_single_part_bug
from camrcs.utils import run, setup_logging, total_run_time


def down(keep, target):
    """Retrieve data from RCS"""
    setup_logging()
    # start run timer
    start = timeit.default_timer()

    # open data.csv
    csv = read_csv()

    # select row with relevant information
    row = csv.loc[target]

    # get info
    crsid = row["crsid"]
    project_dir = row["project_dir"]
    target_dir = row["target_dir"]
    download_dir = row["download_dir"]
    remote_dest_dir = row["remote_dest_dir"]
    md5sum_up = row["md5sum_up"]

    logging.info(
        f"Retrieving archive {os.path.join(project_dir,remote_dest_dir)} from RCS..."
    )

    # perform some checks
    if type(download_dir) != str:
        logging.error("download_dir is not a valid path (no value in data.csv?)...")
        sys.exit()

    # create rsync command
    archive = f"{os.path.basename(target_dir)}.tar.gz.part-"
    remote_dir = f"{crsid}@{remote_host(project_dir)}:{os.path.join(project_dir,remote_dest_dir)}"
    if has_single_part_bug(row.get("version")) and remote_path_is_file(remote_dir):
        logging.warning(
            "remote_dest_dir is a file: it is the only part of the archive (see single-part upload bug)..."
        )
        # restore the name of the part, as it was lost on upload
        os.makedirs(download_dir, exist_ok=True)
        part = os.path.join(download_dir, f"{archive}aa")
        rsync = f"rsync -v -h {remote_dir} {part}"
    else:
        rsync = f"rsync -v -h {remote_dir}/{archive}* {download_dir}"
    logging.info(f"Running command: {rsync}")

    if run(rsync):
        date_down = str(datetime.now().astimezone())

    logging.info("Concatenating archive parts...")

    # concatenate each part in a for loop and delete each part as you go
    # this will prevent the need for a large amount of disk space
    archive = os.path.join(download_dir, os.path.basename(target_dir)) + ".tar.gz"
    parts = f"{archive}.part-*"
    cat = f"for f in $(ls {parts}); do cat $f >> {archive}; rm $f; done"

    if run(cat):
        logging.info(f"Calculating md5sum for retrieved archive...")
        md5sum_down = md5(archive)
        logging.info("Done...")
        logging.info(f"Comparing md5sum of uploaded archive vs retrieved archive...")

    if md5sum_down == md5sum_up:
        logging.info("Retrieved archive correct...")

    else:
        logging.error(f"Retrieved archive incorrect...\nRun camrcs again!")
        sys.exit(1)

    logging.info("Unpacking retrieved archive...")

    # unzipping/unpacking in seperate commands
    # https://superuser.com/questions/841865/extracting-a-tar-gz-file-returns-this-does-not-look-like-a-tar-archive
    unzip_archive = os.path.basename(archive.replace(".gz", ""))

    if keep:
        untar = f"pigz -dk {archive} ; cd {download_dir}; tar -xvf {unzip_archive}; rm {unzip_archive}"
        logging.info(f"Running command: {untar}")
    else:
        os.makedirs(download_dir, exist_ok=True)
        untar = f"pigz -d {archive} ; cd {download_dir}; tar -xvf {unzip_archive}; rm {unzip_archive}"
        logging.info(f"Running command: {untar}")

    if run(untar):
        # update csv with md5 hash/date
        update_csv(target, row, date_down=date_down, md5sum_down=md5sum_down)
        logging.info("Finished!")

    # display total run time
    total_run_time(start)
