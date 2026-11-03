"""camrcs up: archive directories and upload them"""

from datetime import datetime
import glob
import logging
import os
from os import path
from pathlib import Path
import sys
import time
import timeit

import numpy as np

from camrcs import VERSION, data_csv
from camrcs.checksums import read_md5sum_file
from camrcs.data_csv import read_csv, update_csv
from camrcs.manifest import write_manifest
from camrcs.remote import remote_host
from camrcs.utils import convert_bytes, run, setup_logging, total_run_time


def file_size(archive):
    """calculates total size of split archive files"""
    # Calculate total size of list of files
    file_list = glob.glob(f"{archive}.part-*")
    size = sum(os.path.getsize(f) for f in file_list if os.path.isfile(f))

    return convert_bytes(size)


def up(csv, keep):
    """Upload data to RCS"""
    setup_logging()
    # Start total run timer
    start = timeit.default_timer()
    # Create empty data.csv if requested
    if csv:
        logging.info("Creating new data.csv")
        header = "id,crsid,project_dir,date_up,date_down,temp_path,target_dir,remote_dest_dir,chunk_size,exclude_dir,md5sum_up,md5sum_down,archive_size,download_dir,version"
        csv_file = os.path.join(data_csv.cdir, "data.csv")
        if not os.path.exists(csv_file):  # do not overwrite existing data.csv!
            # write to file
            with open(csv_file, "w") as text_file:
                print(header, file=text_file)
            return
        else:
            logging.error("data.csv already exists!")
            sys.exit(1)

    # Open data.csv
    csv = read_csv()

    # Get directories that have to be uploaded (no date for upload)
    csv_up = csv[csv["date_up"].isnull()]

    # Total number of archives to upload
    total = len(csv_up)

    # Exit if all directories have been uploaded already to RCS
    if total == 0:
        logging.warning("Nothing to upload to RCS!")
        return

    # Upload data
    for index, row in csv_up.iterrows():
        # Get info
        crsid = row["crsid"]
        project_dir = row["project_dir"]
        host = remote_host(project_dir)
        temp_path = row["temp_path"]
        target_dir = row["target_dir"]
        remote_dest_dir = row["remote_dest_dir"]
        chunk_size = row["chunk_size"]
        exclude = row["exclude_dir"]

        md5sum_file = os.path.join(
            temp_path, f"md5sum_{os.path.basename(target_dir)}.txt"
        )

        if type(exclude) == float or exclude == np.nan:
            exclude = ""
        else:
            exclude = f"--exclude={exclude}"

        if chunk_size == np.nan:
            raise ValueError("chunk_size is not defined in data.csv")

        # Check if target directory exists
        if not path.exists(target_dir):
            logging.error(f"target_dir ({target_dir}) does not exist!")
            continue  # go to next dir if any

        # Tar file name
        archive = os.path.join(temp_path, f"{os.path.basename(target_dir)}.tar.gz")
        logging.info(f"Creating archive for {target_dir} at RCS...")

        # Path where the md5sum is persisted alongside the split archive
        md5sum_cache = f"{archive}.md5sum"

        # Check if archive has been split before
        if not os.path.exists(f"{archive}.split.done"):
            # Create archive
            logging.info(f"Creating split {archive} ...")

            target_base = os.path.dirname(target_dir)
            target_name = os.path.basename(target_dir)

            tar = f'tar -vc -C {target_base} {exclude} {target_name} | pigz | tee >(md5sum > "{md5sum_file}") | split -b {chunk_size} - {archive}.part-'
            logging.info(f"Running command: {tar}")
            time.sleep(5)

            if run(tar):
                Path(os.path.join(f"{archive}.split.done")).touch()
                # Persist md5sum so it survives a failed rsync on re-run
                md5sum_up = read_md5sum_file(md5sum_file)
                with open(md5sum_cache, "w") as f:
                    f.write(md5sum_up)
        else:
            logging.info(f"{archive} has been created and split before...")
            if not os.path.exists(md5sum_cache):
                logging.error(f"MD5 sum cache not found: {md5sum_cache}")
                sys.exit(1)
            md5sum_up = open(md5sum_cache).read().strip()

        # store a description of the archive alongside its parts on RDV
        manifest_file = ""
        if host == "rdv.uis.cam.ac.uk":
            manifest_file = write_manifest(archive, index, row, md5sum_up)

        # wait for user input (otherwise rsync can timeout if user does not promptly enter password)
        # this should stay directly before rsync, after all slow steps
        logging.info("Transferring split archive files to RCS...")
        input("Press Enter to continue...")

        # trailing slash: without it a single-part archive is written as a file named remote_dest_dir
        rsync = f"rsync -v -h --progress $(ls {archive}.part-*) {manifest_file} {crsid}@{host}:{project_dir}/{remote_dest_dir}/"
        logging.info(f"Running command: {rsync}")
        if run(rsync):
            # update csv with md5sum hash/date
            saved = update_csv(
                index,
                row,
                md5sum_up=md5sum_up,
                date_up=str(datetime.now().astimezone()),
                version=VERSION,
                archive_size=file_size(archive),
            )

            # do not remove the only local copy of an upload that was not recorded
            if not saved:
                logging.error(f"Keeping all archive files of {archive}...")
                continue

        # remove archive and split archive files
        if not keep:
            logging.info("Removing all archive files...")
            run(f"rm -r {archive}*")
        else:
            logging.info("Keeping all split archive files...")

    logging.info("Finished!")

    # display total run time
    total_run_time(start)
