=============
User guide
=============


All options
-------------

.. click:: camrcs:up
   :prog: camrcs up
   :nested: full


.. click:: camrcs:down
   :prog: camrcs down
   :nested: full


.. click:: camrcs:version
   :prog: camrcs version
   :nested: full


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


Creating remote destination directory on RCS
-----------------------------------------------

Due to an older version of ``rsync`` running on the RCS server, it is currently not possible to create a multiple level path set by `remote_dest_dir` in *data.csv* if at least two levels of this path do not yet exist.

In this case, the user has to create this path manually using ``sftp``.

For example, to store data in the new path `data/exp1` run:

.. code-block:: console
   
    $ sftp <crsid>@rcs.uis.cam.ac.uk
    $ Password:
    $ Connected to rcs.uis.cam.ac.uk.
    $ cd rcs-<PIs CRSID>-<Project Name>
    $ mkdir data
    $ mkdir data/exp1
    $ quit


.. note:: If `remote_dest_dir` is a path with only one level or when only the lowest level does not yet exist, then this step can be skipped.

Archive data to RCS
----------------------

To archive data to RCS:

.. code-block:: console
   
    $ cd path/to/data.csv
    $ camrcs up

``camrcs`` will then proceed to archive all directories specified in *data.csv*.

The workflow consists of the following steps:

    1. Creation of compressed tar file of target directory
    2. Generation of md5sum of tar file
        * This can be used to check data integrity when retrieving the archive from RCS
    3. Splitting of tar file into multiple parts
        * The split file size can be set in *data.csv* under the *chunk_size* header
    4. Uploading of split tar file to RCS


Retrieve data from RCS
-------------------------

To retrieve data from RCS:

.. code-block:: console
   
    $ cd path/to/data.csv
    $ camrcs down -t 1

The value of the ``-t`` flag should correspond to the ``id`` header in *data.csv*.

The workflow consists of the following steps:

    1. Retrieval of split archive files from RCS
    2. Concatenation of split archive files into one archive file
    3. Generation of md5sum of assembled tar file
    4. Comparison of md5sums (uploaded data vs retrieved data)
    5. Extraction of compressed archive file to destination directory
    6. Removal of split archive files




