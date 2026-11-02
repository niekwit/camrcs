import argparse
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
import json
import logging
import shutil
from importlib.metadata import version
import pandas as pd
import numpy as np

VERSION = version("camrcs")

# Uploads by earlier versions may have stored a single-part archive as a file
# named remote_dest_dir, instead of inside a directory of that name
SINGLE_PART_FIX_VERSION = (0, 10, 0)

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


def remote_host(project_dir):
    """Returns login address of the storage service that holds project_dir"""
    if project_dir.startswith("/rdv"):
        return "rdv.uis.cam.ac.uk"
    elif project_dir.startswith("/rcs"):
        return "rcs.uis.cam.ac.uk"

    logging.error(f"project_dir ({project_dir}) should start with /rcs or /rdv!")
    sys.exit(1)


def json_value(value):
    """Converts a value from data.csv for JSON (empty values are NaN)"""
    return value if type(value) == str else None


def write_manifest(archive, entry, row, md5sum_up):
    """Writes a manifest describing an archive, to be stored alongside its parts"""
    parts = {}
    for part in sorted(glob.glob(f"{archive}.part-*")):
        logging.info(f"Calculating md5sum for {part}...")
        parts[part.split(".")[-1]] = {"size": os.path.getsize(part), "md5": md5(part)}

    manifest = {
        "id": int(entry),
        "archive": os.path.basename(archive),
        "target_dir": row["target_dir"],
        "project_dir": row["project_dir"],
        "remote_dest_dir": row["remote_dest_dir"],
        "date_created": str(datetime.now().astimezone()),
        "camrcs_version": VERSION,
        "md5sum_up": md5sum_up,
        "parts": parts,
    }

    manifest_file = f"{archive}.manifest.json"
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2)

    return manifest_file


def fits_in_one_part(archive_size, chunk_size):
    """Checks if an archive may consist of one part, if sizes in data.csv allow it"""
    size_units = {"MB": 1e6, "GB": 1e9, "TB": 1e12}
    chunk_units = {"K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}

    try:
        size, size_unit = archive_size.split()
        # the size is rounded to one decimal, so it may be up to 0.05 smaller
        size = (float(size) - 0.05) * size_units[size_unit]
        chunk = float(chunk_size[:-1]) * chunk_units[chunk_size[-1]]
    except (AttributeError, KeyError, ValueError):  # size not recorded or not known
        return True

    return size <= chunk


def has_single_part_bug(upload_version):
    """Checks if a version from data.csv predates the single-part upload fix"""
    if type(upload_version) != str:  # no version recorded (older data.csv)
        return True

    return tuple(int(x) for x in upload_version.split(".")) < SINGLE_PART_FIX_VERSION


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


def test_csv():
    assert os.path.exists(os.path.join(cdir, "data.csv")) == True, "data.csv not found!"


#### Command functions ####


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


def usage():
    """Print how much data has been uploaded to RCS."""
    setup_logging()
    # open data.csv
    csv = pd.read_csv(os.path.join(cdir, "data.csv"))

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


def manifest():
    """Create one manifest for all entries uploaded to RCS, from data.csv"""
    setup_logging()
    # open data.csv
    csv = read_csv()

    # select entries uploaded to RCS
    is_rcs = csv["project_dir"].str.startswith("/rcs", na=False)
    csv_rcs = csv[is_rcs & csv["date_up"].notnull()]

    entries = []
    for index, row in csv_rcs.iterrows():
        version = row.get("version")
        archive_size = row.get("archive_size")
        chunk_size = row["chunk_size"]

        entries.append(
            {
                "id": int(index),
                "archive": f"{os.path.basename(row['target_dir'])}.tar.gz",
                "target_dir": row["target_dir"],
                "project_dir": row["project_dir"],
                "remote_dest_dir": row["remote_dest_dir"],
                "date_up": row["date_up"],
                "camrcs_version": json_value(version),
                "md5sum_up": json_value(row["md5sum_up"]),
                "archive_size": json_value(archive_size),
                "chunk_size": json_value(chunk_size),
                # remote_dest_dir may be the archive itself: this needs checking on the server
                "may_be_stored_as_file": bool(
                    has_single_part_bug(version)
                    and fits_in_one_part(archive_size, chunk_size)
                ),
            }
        )

    manifest_file = os.path.join(cdir, "rcs_manifest.json")
    with open(manifest_file, "w") as f:
        json.dump(entries, f, indent=2)

    logging.info(f"Wrote {len(entries)} RCS entries to {manifest_file}")


#### Command line parser ####


def main():
    parser = argparse.ArgumentParser(
        description="Management of data backups to/from Cambridge University Research Cold Storage (RCS)"
    )
    subparsers = parser.add_subparsers(dest="command")

    # up
    up_parser = subparsers.add_parser("up", help="Upload data to RCS")
    up_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep split archive files of target dir",
    )
    up_parser.add_argument(
        "-c",
        "--csv",
        action="store_true",
        help="Create empty data.csv file in current directory",
    )

    # down
    down_parser = subparsers.add_parser("down", help="Retrieve data from RCS")
    down_parser.add_argument(
        "-k",
        "--keep",
        action="store_true",
        help="Keep retrieved compressed archive after unpacking",
    )
    down_parser.add_argument(
        "-t", "--target", type=int, help="Target archive (id) to retrieve from RCS"
    )

    # usage
    subparsers.add_parser(
        "usage",
        help="Print how much data has been uploaded to RCS. "
        "Calculated from data.csv, not by connecting to the RCS server.",
    )

    # manifest
    subparsers.add_parser(
        "manifest",
        help="Create rcs_manifest.json with all entries uploaded to RCS. "
        "Calculated from data.csv, not by connecting to the RCS server.",
    )

    # version
    subparsers.add_parser("version", help="Print version and quit")

    args = parser.parse_args()

    if args.command == "up":
        up(args.csv, args.keep)
    elif args.command == "down":
        down(args.keep, args.target)
    elif args.command == "usage":
        usage()
    elif args.command == "manifest":
        manifest()
    elif args.command == "version":
        print(f"camrcs v{VERSION}")
    else:
        parser.print_help()
