"""Save flow of the app: ask where to save a cached model, confirm overwrites, copy, report problems.

The dialogs are injectable (choose, confirm, report) so tests and the window can replace them. The core service never asks
the user: overwrite=True is passed only after the user said yes. Runs on the GUI thread (a file copy).
"""
from pathlib import Path
from typing import Callable, Sequence

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from core.cache import Entry
from core.jobs import SaveError, default_save_name, find_conflicts, save

MAX_LISTED = 8
FILTERS = {".csv": "CSV files (*.csv);;All files (*)", ".txt": "Text files (*.txt);;All files (*)",
           ".step": "STEP files (*.step);;All files (*)"}


def choose_destination(parent: QWidget | None, start: Path, is_folder: bool) -> Path | None:
    if is_folder:
        # a folder dialog picks the parent, so an existing folder of the same name can be chosen again
        parent_dir = QFileDialog.getExistingDirectory(parent, "Save in folder", str(start.parent))
        return Path(parent_dir) / start.name if parent_dir else None
    filters = FILTERS.get(start.suffix.lower(), "All files (*)")
    name, _ = QFileDialog.getSaveFileName(parent, "Save", str(start), filters,
                                          options=QFileDialog.DontConfirmOverwrite)
    return Path(name) if name else None


def overwrite_text(paths: Sequence[Path]) -> str:
    shown = [str(p) for p in paths[:MAX_LISTED]]
    text = "These files already exist and will be replaced:\n" + "\n".join(shown)
    if len(paths) > MAX_LISTED:
        text += "\nand %d more" % (len(paths) - MAX_LISTED)
    return text


def confirm_overwrite(parent: QWidget | None, paths: Sequence[Path]) -> bool:
    answer = QMessageBox.question(parent, "Overwrite?", overwrite_text(paths), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
    return answer == QMessageBox.Yes


def report_save_error(parent: QWidget | None, message: str) -> None:
    QMessageBox.critical(parent, "Save failed", message)


def run_save(entry: Entry, start_dir: Path, *, parent=None, choose=choose_destination, confirm=confirm_overwrite,
             report=report_save_error) -> list[Path] | None:
    """Returns the written paths, or None when the user cancelled or declined, or after reporting a failure."""
    main = entry.outputs[0]
    is_folder = main.is_dir()
    dest = choose(parent, Path(start_dir) / default_save_name(entry), is_folder)
    if dest is None:
        return None
    dest = Path(dest)
    if not is_folder and not dest.suffix and not dest.is_dir():
        dest = dest.with_suffix(main.suffix)
    try:
        conflicts = find_conflicts(entry, dest)
        if conflicts and not confirm(parent, conflicts):
            return None
        return save(entry, dest, overwrite=bool(conflicts))
    except SaveError as e:
        report(parent, str(e))
        return None
