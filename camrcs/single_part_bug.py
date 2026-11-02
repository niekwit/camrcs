"""Detection of archives affected by the single-part upload bug"""

# Uploads by earlier versions may have stored a single-part archive as a file
# named remote_dest_dir, instead of inside a directory of that name
SINGLE_PART_FIX_VERSION = (0, 10, 0)


def has_single_part_bug(upload_version):
    """Checks if a version from data.csv predates the single-part upload fix"""
    if type(upload_version) != str:  # no version recorded (older data.csv)
        return True

    return tuple(int(x) for x in upload_version.split(".")) < SINGLE_PART_FIX_VERSION


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
