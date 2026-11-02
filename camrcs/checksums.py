"""MD5 sums of archives and their parts"""

import glob
import hashlib
import json
import logging
import os


def md5(file):
    """Calculates MD5sum of input file"""
    hash_md5 = hashlib.md5()

    # open file in smaller chunks to avoid memory issues
    with open(file, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


def read_md5sum_file(file):
    """Reads md5sum file and returns md5sum hash"""
    with open(file) as f:
        md5sum = f.readline().split("  ")[0]

    return md5sum


def part_md5sums(archive):
    """Calculates size and md5sum of each archive part, saving progress for a re-run"""
    cache_file = f"{archive}.part_md5sums.json"
    temp_file = f"{cache_file}.tmp"

    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)

    parts = {}
    for part in sorted(glob.glob(f"{archive}.part-*")):
        name = part.split(".")[-1]
        info = os.stat(part)
        size, modified = info.st_size, info.st_mtime_ns

        # size and time of last modification rule out a part that was created again
        cached = cache.get(name, {})
        if cached.get("size") == size and cached.get("modified") == modified:
            logging.info(f"Using saved md5sum for {part}...")
            continue

        logging.info(f"Calculating md5sum for {part}...")
        cache[name] = {"size": size, "modified": modified, "md5": md5(part)}

        # atomic, as camrcs can be cancelled at any time
        with open(temp_file, "w") as f:
            json.dump(cache, f, indent=2)
        os.replace(temp_file, cache_file)

    for part in sorted(glob.glob(f"{archive}.part-*")):
        name = part.split(".")[-1]
        parts[name] = {"size": cache[name]["size"], "md5": cache[name]["md5"]}

    return parts
