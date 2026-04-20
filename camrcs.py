import click
import os
import sys
import os.path
from os import path
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime
import time
import timeit
import glob
import logging
from importlib.metadata import version
import pandas as pd
import numpy as np

VERSION = version("camrcs")


def setup_logging():
    date_time = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")
    log = f"camrcs_{date_time}.log"
    logging.basicConfig(
        format="%(levelname)s:%(asctime)s: %(message)s",
        level=logging.DEBUG,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.FileHandler(log), logging.StreamHandler()],
    )


# Get current working dir
cdir = os.getcwd()

#### Python functions ####


def md5(file):
    """Calculates MD5sum of input file"""
    hash_md5 = hashlib.md5()

    # open file in smaller chunks to avoid memory issues
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


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


def update_csv(csv):
    """Updates data.csv"""
    # Overwrite csv with md5 hash/date
    logging.info("Updating data.csv...")
    csv.to_csv("data.csv")


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


def file_size(archive):
    """calculates total size of split archive files"""
    # Calculate total size of list of files
    file_list = glob.glob(f"{archive}.part-*")
    size = sum(os.path.getsize(f) for f in file_list if os.path.isfile(f))

    return convert_bytes(size)


def read_md5sum_file(file):
    """Reads md5sum file and returns md5sum hash"""
    with open(file) as f:
        md5sum = f.readline().split("  ")[0]

    return md5sum


def test_csv():
    assert os.path.exists(os.path.join(cdir, "data.csv")) == True, "data.csv not found!"


#### Command line parser ####
@click.group()
def cli():
    """Management of data backups to/from Cambridge University Research Cold Storage (RCS)"""


# Define subparser for uploading data to RCS
@click.command(name="up")
@click.option(
    "-k", "--keep", is_flag=True, help="Keep split archive files of target dir"
)
@click.option(
    "-c", "--csv", is_flag=True, help="Create empty data.csv file in current directory"
)
def up(csv, keep):
    """Upload data to RCS"""
    setup_logging()
    # Start total run timer
    start = timeit.default_timer()
    # Create empty data.csv if requested
    if csv:
        logging.info("Creating new data.csv")
        header = "id,crsid,project_dir,date_up,date_down,temp_path,target_dir,remote_dest_dir,chunk_size,exclude_dir,md5sum_up,md5sum_down,archive_size,download_dir,version"
        csv_file = os.path.join(cdir, "data.csv")
        if not os.path.exists(csv_file):  # do not overwrite existing data.csv!
            # write to file
            with open(csv_file, "w") as text_file:
                print(header, file=text_file)
            return
        else:
            logging.error("data.csv already exists!")
            sys.exit(1)

    # Open data.csv
    csv = pd.read_csv(os.path.join(cdir, "data.csv"))
    csv = csv.set_index("id")

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

        # wait for user input (otherwise rsync can timeout if user does not promptly enter password)
        logging.info("Transferring split archive files to RCS...")
        input("Press Enter to continue...")

        rsync = f"rsync -v -h --progress $(ls {archive}.part-*) {crsid}@rcs.uis.cam.ac.uk:{project_dir}/{remote_dest_dir}"
        logging.info(f"Running command: {rsync}")
        if run(rsync):
            # update csv
            csv.at[index, "md5sum_up"] = md5sum_up
            csv.at[index, "date_up"] = str(datetime.now().astimezone())

            try:  # these columns might not exist if data.csv was created with older version of camrcs
                csv.at[index, "version"] = VERSION
                csv.at[index, "archive_size"] = file_size(archive)
            except KeyError:  # just print to console
                logging.info(f"Total archive size is {file_size(archive)}")

        # update csv with md5sum hash/date
        update_csv(csv)

    # remove archive and split archive files
    if not keep:
        logging.info("Removing all archive files...")
        remove = f"rm -r {archive}*"
    else:
        logging.info("Keeping all split archive files...")
    if run(remove):
        logging.info("Finished!")

    # display total run time
    total_run_time(start)


# define subparser for retrieving data from RCS
@click.command(name="down")
@click.option(
    "-k", "--keep", is_flag=True, help="Keep split archive files of target dir"
)
@click.option(
    "-t", "--target", type=int, help="Target archive (id) to retrieve from RCS"
)
def down(keep, target):
    """Retrieve data from RCS"""
    setup_logging()
    # start run timer
    start = timeit.default_timer()

    # open data.csv
    csv = pd.read_csv(os.path.join(cdir, "data.csv"))
    csv = csv.set_index("id")

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
    archive = f"{os.path.basename(target_dir)}.tar.gz.part-*"
    archive = f"{os.path.join(project_dir,remote_dest_dir,archive)}"
    rsync = f"rsync -v -h {crsid}@rcs.uis.cam.ac.uk:{archive} {download_dir}"
    logging.info(f"Running command: {rsync}")

    if run(rsync):
        csv.at[target, "date_down"] = str(datetime.now().astimezone())

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
        csv.at[target, "md5sum_down"] = md5sum_down

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
        update_csv(csv)
        logging.info("Finished!")

    # display total run time
    total_run_time(start)


@click.command(name="usage")
def usage():
    """Print how much data has been uploaded to RCS.
    This is calculated from the data.csv file and not by connecting to the RCS server.
    """
    setup_logging()
    # open data.csv
    csv = pd.read_csv(os.path.join(cdir, "data.csv"))

    # get size of each archive
    archive_size = csv["archive_size"]

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

    logging.info(f"Total size of all archives on RCS: {convert_bytes(total_size)}")


@click.command(name="version")
def version():
    """Print version and quit"""
    click.secho(f"camrcs v{VERSION}", fg="green")


# add subparsers
cli.add_command(up)
cli.add_command(down)
cli.add_command(version)
cli.add_command(usage)
