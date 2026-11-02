# CAMRCS

`camrcs` is a Python package that manages data backups to Cambridge University Research DataVault (RDV) and Research Cold Storage (RCS). RCS is now read-only, so new uploads should go to RDV.

Complete documentation can be found [here](https://camrcs.readthedocs.io/en/stable/index.html).

## QUICKSTART

### Installation

Install `pigz` first:

```
sudo apt-get install pigz
```

Then install `camrcs` (requires Python 3.14 or later and `rsync`):

```bash
pip install camrcs
```

### Before first use

`camrcs` requires a _data.csv_ file that stores information of what to upload, etc.

To create a new _data.csv_ run:

```bash
cd any/path/to/store/file
camrcs up --csv
```

### Uploading data

First include all relevant information in _data.csv_. The login address follows from `project_dir`, which should start with `/rdv` or `/rcs`. Then run from the directory containing _data.csv_:

```bash
camrcs up
```

This will upload all data that has not yet been uploaded.

### Retrieving data

For example, to retrieve the archive with `id` 1 from _data.csv_ run:

```bash
camrcs down -t 1
```
