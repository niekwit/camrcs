import subprocess
from types import SimpleNamespace

import pandas as pd
import pytest

import camrcs

HEADER = "id,crsid,project_dir,date_up,date_down,temp_path,target_dir,remote_dest_dir,chunk_size,exclude_dir,md5sum_up,md5sum_down,archive_size,download_dir,version"


@pytest.mark.parametrize(
    "project_dir, host",
    [
        ("/rdv/project/abc", "rdv.uis.cam.ac.uk"),
        ("/rcs/project/abc", "rcs.uis.cam.ac.uk"),
    ],
)
def test_remote_host(project_dir, host):
    assert camrcs.remote_host(project_dir) == host


def test_remote_host_unknown_project_dir():
    with pytest.raises(SystemExit):
        camrcs.remote_host("/data/project/abc")


@pytest.mark.parametrize(
    "version, expected",
    [
        ("0.7", True),
        ("0.8.0", True),
        ("0.9.0", True),
        ("0.10.0", False),
        ("0.11.0", False),
        (float("nan"), True),
        (None, True),
    ],
)
def test_has_single_part_bug(version, expected):
    assert camrcs.has_single_part_bug(version) == expected


@pytest.mark.parametrize(
    "listing, expected",
    [
        ("-rw-r--r--  978,000,000 2026/06/16 14:23:00 Hudson\n", True),
        ("drwxr-sr-x  4,096 2026/06/16 14:23:00 Hudson\n", False),
        ("Welcome to the server\n-rw-r--r--  1 2026/06/16 14:23:00 Hudson\n", True),
    ],
)
def test_remote_path_is_file(monkeypatch, listing, expected):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=listing),
    )
    assert camrcs.remote_path_is_file("nw416@host:/path") == expected


def write_upload_csv(path, names):
    """Writes data.csv with entries that have not been uploaded yet, each with a split archive"""
    temp_path = path / "tmp"
    temp_path.mkdir()
    rows = [HEADER]
    for index, name in enumerate(names, start=1):
        (path / name).mkdir()
        for suffix in ["part-aa", "split.done"]:
            (temp_path / f"{name}.tar.gz.{suffix}").touch()
        (temp_path / f"{name}.tar.gz.md5sum").write_text("abc")
        rows.append(
            f"{index},nw416,/rdv/project/abc,,,{temp_path}/,{path / name},ngsdata/{name},1G,,,,,,"
        )
    (path / "data.csv").write_text("\n".join(rows) + "\n")

    return temp_path


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Runs camrcs in a temporary directory, without any transfers"""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(camrcs, "cdir", str(tmp_path))
    monkeypatch.setattr("builtins.input", lambda *args: "")
    run = camrcs.run
    commands = []

    def run_without_transfer(command, message=None):
        commands.append(command)
        return True if command.startswith("rsync") else run(command, message)

    monkeypatch.setattr(camrcs, "run", run_without_transfer)

    return SimpleNamespace(path=tmp_path, commands=commands)


def test_up_records_upload_in_empty_columns(upload_dir):
    # pandas>=3 does not allow strings to be written to columns read as floats
    write_upload_csv(upload_dir.path, ["exp1"])
    camrcs.up(False, False)

    row = pd.read_csv("data.csv").iloc[0]
    assert row["md5sum_up"] == "abc"
    assert row["version"] == camrcs.VERSION
    assert isinstance(row["date_up"], str)


def test_up_uses_trailing_slash(upload_dir):
    write_upload_csv(upload_dir.path, ["exp1"])
    camrcs.up(False, False)

    rsync = next(c for c in upload_dir.commands if c.startswith("rsync"))
    assert rsync.endswith("nw416@rdv.uis.cam.ac.uk:/rdv/project/abc/ngsdata/exp1/")


def test_up_removes_archives_of_all_entries(upload_dir):
    temp_path = write_upload_csv(upload_dir.path, ["exp1", "exp2"])
    camrcs.up(False, False)

    assert list(temp_path.iterdir()) == []


def test_up_keep(upload_dir):
    temp_path = write_upload_csv(upload_dir.path, ["exp1", "exp2"])
    camrcs.up(False, True)

    assert len(list(temp_path.iterdir())) == 6
