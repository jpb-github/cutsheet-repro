"""About box: what the app is and, above all, which version it is (the VERSION file next to the app folder, shipped by the installer)."""
from pathlib import Path

from PySide6.QtWidgets import QMessageBox, QWidget

APP_NAME = "Cutsheet Generator"
DESCRIPTION = "Generates cutsheets for the fabrication of wood furniture: the list of pieces to cut, and how to cut them."
VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"


def read_version(path: Path = VERSION_FILE) -> str:
    """The version text of the VERSION file, "unknown" when it cannot be read."""
    try:
        return Path(path).read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def about_text(version: str | None = None) -> str:
    return "<h3>%s</h3><p><b>Version %s</b></p><p>%s</p>" % (APP_NAME, version or read_version(), DESCRIPTION)


def show_about(parent: QWidget | None = None) -> None:
    QMessageBox.about(parent, "About %s" % APP_NAME, about_text())
