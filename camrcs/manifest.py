"""Manifests describing archives: one per RDV upload, and one for all of RCS"""

from datetime import datetime
import json
import logging
import os

from camrcs import VERSION, data_csv
from camrcs.checksums import part_md5sums
from camrcs.data_csv import read_csv
from camrcs.single_part_bug import fits_in_one_part, has_single_part_bug
from camrcs.utils import setup_logging


def json_value(value):
    """Converts a value from data.csv for JSON (empty values are NaN)"""
    return value if type(value) == str else None


def write_manifest(archive, entry, row, md5sum_up):
    """Writes a manifest describing an archive, to be stored alongside its parts"""
    parts = part_md5sums(archive)

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


def rcs_manifest():
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

    manifest_file = os.path.join(data_csv.cdir, "rcs_manifest.json")
    with open(manifest_file, "w") as f:
        json.dump(entries, f, indent=2)

    logging.info(f"Wrote {len(entries)} RCS entries to {manifest_file}")
