=============
User guide
=============

RCS and RDV
-------------

``camrcs`` works with both Research Cold Storage (RCS) and its replacement, `Research DataVault (RDV) <https://docs.hpc.cam.ac.uk/storage/rdv/index.html>`_. The login address is selected for each entry from `project_dir` in *data.csv*:

.. csv-table::
   :header: "project_dir starts with", "Login address"

   "``/rdv``", "``rdv.uis.cam.ac.uk``"
   "``/rcs``", "``rcs.uis.cam.ac.uk``"

``camrcs`` stops with an error if `project_dir` starts with anything else.

.. warning:: RCS is now read-only, so new uploads should go to RDV. Once data has moved to RDV, update `project_dir` of the entries in *data.csv*.


All options
-------------

``camrcs up``: upload all entries in *data.csv* without a value for `date_up`.

.. csv-table::
   :header: "Option", "Description"
   :widths: 20, 80

   "``-k``, ``--keep``", "Keep split archive files of target dir"
   "``-c``, ``--csv``", "Create empty *data.csv* file in current directory"

``camrcs down``: retrieve one archive.

.. csv-table::
   :header: "Option", "Description"
   :widths: 20, 80

   "``-t``, ``--target``", "Target archive (``id`` in *data.csv*) to retrieve"
   "``-k``, ``--keep``", "Keep the retrieved compressed archive (*.tar.gz*) after unpacking"

``camrcs usage``: print the estimated size of all uploaded archives. This is calculated from *data.csv*, without connecting to the server.

``camrcs manifest``: write *rcs_manifest.json* with all entries uploaded to RCS. See `Manifests`_.

``camrcs version``: print version and quit.

All commands should be run from the directory containing *data.csv*. Each run of ``up``, ``down`` and ``usage`` writes a log file to this directory.


Create data.csv file
-----------------------

``camrcs`` requires a *data.csv* file that contains the information for all directories that need to be archived:

.. csv-table:: data.csv
   :file: data_pre.csv
   :header-rows: 1


An empty *data.csv* file can be generated before first use:

.. code-block:: console

    $ cd path/to/storefile
    $ camrcs up --csv

`date_up`, `date_down`, `md5sum_up`, `md5sum_down`, `archive_size` and `version` are filled in by ``camrcs``. `download_dir` is only used by ``camrcs down``, so it can be added when an archive is retrieved.

.. warning:: Check `remote_dest_dir` before uploading. Files may not be renamed or moved on the server afterwards.


Creating remote destination directory
-----------------------------------------------

``rsync`` only creates the last directory of `remote_dest_dir`. If higher levels of this path do not yet exist, the user has to create them manually using ``sftp``, connecting to the login address for `project_dir`.

For example, to store data in the new path `data/exp1` run:

.. code-block:: console

    $ sftp <crsid>@rdv.uis.cam.ac.uk
    Password:
    Connected to rdv.uis.cam.ac.uk.
    sftp> cd <project_dir>
    sftp> mkdir data
    sftp> mkdir data/exp1
    sftp> quit


.. note:: If `remote_dest_dir` is a path with only one level or when only the lowest level does not yet exist, then this step can be skipped.

Archive data
----------------------

To archive data:

.. code-block:: console

    $ cd path/to/data.csv
    $ camrcs up

``camrcs`` will then proceed to archive all directories specified in *data.csv* that have not been uploaded yet.

The workflow consists of the following steps for each directory:

    1. Creation of compressed tar file of target directory
    2. Generation of md5sum of tar file
        * This can be used to check data integrity when retrieving the archive
    3. Splitting of tar file into multiple parts
        * The split file size can be set in *data.csv* under the *chunk_size* header
    4. Pressing Enter to start the upload, followed by logging in
        * The upload starts on request, as ``rsync`` can time out if the login is not completed promptly
    5. Uploading of split tar file, and for RDV also a manifest (see `Manifests`_)
    6. Removal of the local split tar files in `temp_path`, unless ``--keep`` is used


Manifests
-------------------------

Each upload to RDV includes a file named *<target directory>.tar.gz.manifest.json* alongside the split tar files. It describes the archive without needing *data.csv*: the entry in *data.csv*, its paths, the ``camrcs`` version, the md5sum of the archive, and the size and md5sum of each part. Generating the md5sum of each part adds some time before the upload.

Files already on RCS have no manifest, as RCS is read-only. To record these entries in one file:

.. code-block:: console

    $ cd path/to/data.csv
    $ camrcs manifest

This writes *rcs_manifest.json* from *data.csv*, without connecting to the server. `may_be_stored_as_file` is true for entries that could be affected by the single-part upload bug (see `Retrieve data`_). The sizes in *data.csv* can only show that this is possible, so check these entries on the server.

Keep *data.csv* safe too. ``camrcs`` keeps the previous version as *data.csv.bak* each time it updates the file.


Retrieve data
-------------------------

To retrieve data:

.. code-block:: console

    $ cd path/to/data.csv
    $ camrcs down -t 1

The value of the ``-t`` flag should correspond to the ``id`` header in *data.csv*. `download_dir` must be set for this entry.

.. note::
   Before version 0.10.0, an archive consisting of a single part could be stored as a file named `remote_dest_dir`, if that directory did not yet exist. ``camrcs down`` detects this for entries in *data.csv* uploaded with these versions, which requires one extra login.

The workflow consists of the following steps:

    1. Retrieval of split archive files
    2. Concatenation of split archive files into one archive file, removing each split file along the way
    3. Generation of md5sum of assembled tar file
    4. Comparison of md5sums (uploaded data vs retrieved data)
    5. Extraction of compressed archive file to destination directory
    6. Removal of compressed archive file, unless ``--keep`` is used
