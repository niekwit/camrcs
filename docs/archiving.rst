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


Create data.csv file
-----------------------

``camrcs`` requires a *data.csv* file that contains the information for all directories that need to be archived:

.. csv-table:: data.csv
   :file: data_pre.csv
   :header-rows: 1

An empty *data.csv* file can be generated before first use:

.. code-block:: console
   
    $ cd path/to/storefile
    $ camrcs up --new


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
    4. Uploading or split tar file to RCS


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
    6. Removal of (un)split archive files




