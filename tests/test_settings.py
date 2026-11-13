import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtCore import QStandardPaths  # noqa: E402

from app.settings import documents_dir, last_dir, remember_dir  # noqa: E402


def test_first_launch_defaults_to_my_documents():
    documents = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
    assert documents_dir() == (documents if documents.is_dir() else Path.home())
    assert last_dir() == documents_dir()


def test_a_remembered_folder_comes_back_after_a_restart(tmp_path):
    folder = tmp_path / "my models"
    folder.mkdir()
    remember_dir(folder)
    assert last_dir() == folder
    assert (tmp_path / "cs-settings" / "settings.ini").is_file()          # on disk, so a new launch reads it too
    assert last_dir() == folder                                               # every call reads the file: nothing is cached


def test_a_folder_that_has_vanished_falls_back_to_my_documents(tmp_path):
    folder = tmp_path / "gone soon"
    folder.mkdir()
    remember_dir(folder)
    folder.rmdir()
    assert last_dir() == documents_dir()


def test_remembering_a_file_path_keeps_its_folder(tmp_path):
    (tmp_path / "x").mkdir()
    remember_dir(tmp_path / "x" / "model.step")
    assert last_dir() == tmp_path / "x"
