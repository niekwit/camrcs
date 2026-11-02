import hashlib
import json
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

    assert len(list(temp_path.iterdir())) == 8  # including manifests


def rows(path):
    return pd.read_csv(path / "data.csv").set_index("id")


def test_update_csv_keeps_changes_made_during_run(upload_dir, monkeypatch):
    write_upload_csv(upload_dir.path, ["exp1"])
    run_without_transfer = camrcs.run

    def edit_during_transfer(command, message=None):
        if command.startswith("rsync"):
            with open("data.csv", "a") as f:
                f.write("2,nw416,/rdv/project/abc,,,/tmp/,/added,added,1G,,,,,,\n")
        return run_without_transfer(command, message)

    monkeypatch.setattr(camrcs, "run", edit_during_transfer)
    camrcs.up(False, False)

    csv = rows(upload_dir.path)
    assert csv.loc[2, "target_dir"] == "/added"
    assert csv.loc[1, "md5sum_up"] == "abc"


def test_update_csv_keeps_backup_and_no_temporary_file(upload_dir):
    write_upload_csv(upload_dir.path, ["exp1"])
    before = (upload_dir.path / "data.csv").read_text()
    assert camrcs.update_csv(1, camrcs.read_csv().loc[1], md5sum_up="def")

    assert (upload_dir.path / "data.csv.bak").read_text() == before
    assert not (upload_dir.path / "data.csv.tmp").exists()
    assert rows(upload_dir.path).loc[1, "md5sum_up"] == "def"


def test_update_csv_leaves_data_csv_intact_on_failure(upload_dir, monkeypatch):
    write_upload_csv(upload_dir.path, ["exp1"])
    before = (upload_dir.path / "data.csv").read_text()

    def fail(*args):
        raise OSError

    monkeypatch.setattr(camrcs.os, "replace", fail)
    with pytest.raises(OSError):
        camrcs.update_csv(1, camrcs.read_csv().loc[1], md5sum_up="def")

    assert (upload_dir.path / "data.csv").read_text() == before


def test_update_csv_adds_missing_column(upload_dir):
    # data.csv created with older version of camrcs
    (upload_dir.path / "data.csv").write_text(
        "id,project_dir,target_dir,remote_dest_dir\n1,/rdv/p,/d/exp,x\n"
    )
    camrcs.update_csv(1, camrcs.read_csv().loc[1], version="0.10.0")

    assert rows(upload_dir.path).loc[1, "version"] == "0.10.0"


def test_up_uploads_manifest_to_rdv(upload_dir):
    temp_path = write_upload_csv(upload_dir.path, ["exp1"])
    (temp_path / "exp1.tar.gz.part-aa").write_text("data")
    camrcs.up(False, True)

    manifest_file = temp_path / "exp1.tar.gz.manifest.json"
    manifest = json.loads(manifest_file.read_text())
    assert manifest["id"] == 1
    assert manifest["archive"] == "exp1.tar.gz"
    assert manifest["md5sum_up"] == "abc"
    assert manifest["camrcs_version"] == camrcs.VERSION
    assert manifest["parts"] == {
        "part-aa": {"size": 4, "md5": hashlib.md5(b"data").hexdigest()}
    }

    rsync = next(c for c in upload_dir.commands if c.startswith("rsync"))
    assert str(manifest_file) in rsync


def test_up_does_not_write_manifest_for_rcs(upload_dir):
    temp_path = write_upload_csv(upload_dir.path, ["exp1"])
    csv_file = upload_dir.path / "data.csv"
    csv_file.write_text(csv_file.read_text().replace("/rdv/", "/rcs/"))
    camrcs.up(False, True)

    assert not (temp_path / "exp1.tar.gz.manifest.json").exists()


def test_manifest_contains_uploaded_rcs_entries(upload_dir):
    (upload_dir.path / "data.csv").write_text(
        "\n".join(
            [
                HEADER,
                "1,nw416,/rcs/p,2026,,/t/,/d/single,x,1G,,abc,,978.0 MB,,0.8.0",
                "2,nw416,/rcs/p,2026,,/t/,/d/multi,y,1G,,def,,5.0 GB,,0.9.0",
                "3,nw416,/rcs/p,2026,,/t/,/d/fixed,z,1G,,ghi,,978.0 MB,,0.10.0",
                "4,nw416,/rcs/p,2026,,/t/,/d/oldrow,o,1G,,jkl,,,,",
                "5,nw416,/rcs/p,,,/t/,/d/notup,n,1G,,,,,,",
                "6,nw416,/rdv/p,2026,,/t/,/d/rdv,r,1G,,mno,,1.0 GB,,0.10.0",
            ]
        )
        + "\n"
    )
    camrcs.manifest()

    entries = json.loads((upload_dir.path / "rcs_manifest.json").read_text())
    assert [e["id"] for e in entries] == [1, 2, 3, 4]
    assert [e["may_be_stored_as_file"] for e in entries] == [True, False, False, True]
    assert entries[0]["archive"] == "single.tar.gz"
    assert entries[0]["md5sum_up"] == "abc"
    assert entries[3]["camrcs_version"] is None


@pytest.mark.parametrize(
    "archive_size, chunk_size, expected",
    [
        ("1.1 GB", "1G", True),  # may be 1.06 GB, which fits in a 1G chunk
        ("1.2 GB", "1G", False),
        ("978.0 MB", "1G", True),
        ("203.2 GB", "300G", True),
        (float("nan"), "1G", True),
    ],
)
def test_fits_in_one_part(archive_size, chunk_size, expected):
    assert camrcs.fits_in_one_part(archive_size, chunk_size) == expected


def test_update_csv_does_not_recreate_deleted_entry(upload_dir):
    write_upload_csv(upload_dir.path, ["exp1"])
    row = camrcs.read_csv().loc[1]
    (upload_dir.path / "data.csv").write_text(HEADER + "\n")

    assert not camrcs.update_csv(1, row, md5sum_up="def")
    assert (upload_dir.path / "data.csv").read_text() == HEADER + "\n"


@pytest.mark.parametrize("column", ["project_dir", "target_dir", "remote_dest_dir"])
def test_update_csv_does_not_update_changed_entry(upload_dir, column):
    write_upload_csv(upload_dir.path, ["exp1"])
    row = camrcs.read_csv().loc[1].copy()
    before = (upload_dir.path / "data.csv").read_text()
    row[column] = "/value/before/transfer"

    assert not camrcs.update_csv(1, row, md5sum_up="def")
    assert (upload_dir.path / "data.csv").read_text() == before


def test_up_keeps_archive_if_entry_changed_during_upload(upload_dir, monkeypatch):
    temp_path = write_upload_csv(upload_dir.path, ["exp1", "exp2"])
    run_without_transfer = camrcs.run

    def edit_during_transfer(command, message=None):
        if command.startswith("rsync") and "exp1" in command:
            csv_file = upload_dir.path / "data.csv"
            csv_file.write_text(
                csv_file.read_text().replace("ngsdata/exp1", "ngsdata/moved")
            )
        return run_without_transfer(command, message)

    monkeypatch.setattr(camrcs, "run", edit_during_transfer)
    camrcs.up(False, False)

    # the changed entry is not recorded or removed, the next entry continues as usual
    csv = rows(upload_dir.path)
    assert pd.isnull(csv.loc[1, "date_up"])
    assert csv.loc[1, "remote_dest_dir"] == "ngsdata/moved"
    assert isinstance(csv.loc[2, "date_up"], str)
    assert (temp_path / "exp1.tar.gz.part-aa").exists()
    assert not (temp_path / "exp2.tar.gz.part-aa").exists()
