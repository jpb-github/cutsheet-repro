"""Small persistent settings of the app: the folder every save and open dialog starts in, and the last values of every form.

One remembered folder, shared by every save dialog, and per screen the last valid values of its form (load_form / remember_form,
a JSON text under one key), kept in an .ini file of the user
profile (%APPDATA%\\CutsheetGenerator\\CutsheetGenerator.ini on Windows) so it survives a restart. On the first launch, and when the
remembered folder no longer exists, dialogs start in the user's Documents folder. CUTSHEET_SETTINGS_DIR moves the file (tests use it
so they never touch the real settings), like CUTSHEET_CACHE_DIR does for the cache.
"""
import json
import os
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths

ORGANISATION = "CutsheetGenerator"
APPLICATION = "CutsheetGenerator"
KEY_LAST_DIR = "lastDir"
KEY_FORM = "form/%s"


def _settings() -> QSettings:
    override = os.environ.get("CUTSHEET_SETTINGS_DIR")
    if override:
        folder = Path(override)
        folder.mkdir(parents=True, exist_ok=True)
        return QSettings(str(folder / "settings.ini"), QSettings.IniFormat)
    return QSettings(QSettings.IniFormat, QSettings.UserScope, ORGANISATION, APPLICATION)


def documents_dir() -> Path:
    """The user's Documents folder (it may be redirected, for example to OneDrive); the home folder if it does not exist."""
    documents = Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or "")
    return documents if str(documents) not in ("", ".") and documents.is_dir() else Path.home()


def last_dir() -> Path:
    """Where a save or open dialog should start: the remembered folder if it still exists, else the Documents folder."""
    value = str(_settings().value(KEY_LAST_DIR, "") or "")
    folder = Path(value) if value else None
    return folder if folder is not None and folder.is_dir() else documents_dir()


def remember_dir(path) -> None:
    """Remember a folder for the next dialog and the next launch (a file path is reduced to its folder)."""
    path = Path(path)
    folder = path if path.is_dir() else path.parent
    settings = _settings()
    settings.setValue(KEY_LAST_DIR, str(folder))
    settings.sync()


def load_form(name: str) -> dict:
    """The values remembered for the form `name` ({} when there are none or they cannot be read)."""
    try:
        values = json.loads(str(_settings().value(KEY_FORM % name, "") or "null"))
    except ValueError:
        return {}
    return values if isinstance(values, dict) else {}


def remember_form(name: str, values: dict) -> None:
    """Remember the values of the form `name` for the next launch (JSON-able values: text and booleans)."""
    settings = _settings()
    settings.setValue(KEY_FORM % name, json.dumps(values))
    settings.sync()
