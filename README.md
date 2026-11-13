# Cutsheet Generator

Desktop app (PySide6) that generates cutsheets for the fabrication of wood furniture: the pieces to cut and how to cut them. Modelled on the Multiboard Generator (same layout, style sheet, tests, installer and way of working).

    py -3.14 -m venv .venv
    .venv\Scripts\pip install -r requirements-dev.txt
    .venv\Scripts\python -m app
    .venv\Scripts\python -m pytest

## Tabs

- Drawer Blocks: the pieces of MDF to cut for a block of drawers (outside box, drawers on outside slides, facades), from the available space; the list, with the pocket screws and drawer pulls, is shown live in one list, a perspective view of the block is always drawn under it, Generate saves the list as a CSV. Cutsheet packs the pieces on MDF sheets (size and saw kerf in the form) with edge-to-edge cuts and writes a PDF: a summary, one page per sheet with the numbered cuts, the kerf, the pocket screw marks and the cut instructions, and the pieces drawn large with their dimensions. It searches for 15 s on up to 80 % of the cores; Refine searches further from the last result. All dimensions in mm.

## Files

- `core/` parameters, catalogue, runner, cache, jobs (one part: `drawer_blocks`); `app/` the GUI; `generators/` the generator scripts (`DrawerBlocks`).
- `docs/superpowers/specs`, `plans`: design and task list.
- After editing anything under `generators/` or `seed/`: `python tools/sync_generators.py --update-manifest`.
- `Drawer calculations.xlsx`: the spreadsheet the Drawer Blocks rules started from (some of its formulas were wrong, see the spec).

## Installer and releases

Per-user MSI (needs Python 3.11 to 3.14 from python.org; the libraries are downloaded at the first launch): `python installer/build_msi.py` (needs WiX 5, see the script header) writes `installer/output/CutsheetGenerator-<VERSION>.msi`. The version is the `VERSION` file (three numbers); a release is a commit "version X.Y.Z" tagged `vX.Y.Z`.
