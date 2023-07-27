# CAMRCS

`camrcs` is a Python package that manages data backups to Cambridge University Research Cold Storage (RCS).

Complete documentation can be found [here](https://camrcs.readthedocs.io/en/stable/index.html).

## QUICKSTART

### Installation

Install `pigz` first:

```
sudo apt-get install pigz
```

Then install `camrcs`:

```bash
pip install camrcs
```

### Before first use

`camrcs` requires a *data.csv* file that stores information of what to upload, etc.

To create a new *data.csv* run:

```bash
cd any/path/to/store/file
camrcs up --new

```

### Uploading data to RCS

First include all relevant information in *data.csv*, then run from the directory containing *data.csv*:

```bash
camrcs up
```

This will upload all data that has not yet been uploaded to RCS.

### Retrieving data from RCS

For example, to retrieve the archive with `id` 1 from *data.csv* run:

```bash
camrcs down -t 1
```





