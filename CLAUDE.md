# CLAUDE.md (Cutsheet Generator)

Desktop app (PySide6) that will generate cutsheets for wood furniture fabrication. Modelled on the Multiboard Generator (`../Multiboard Repro`): same layout, same style sheet (`app/theme.py`, identical), same way of working, same installer and release management. Use `.venv` (`.venv\Scripts\python`); recreate it with `py -3.14 -m venv .venv` and `pip install -r requirements-dev.txt`.

## State

Version 0.1.0 (not released). One tab, Drawer Blocks (`app/drawer_blocks_tab.py`): a form generated from the catalogue (available space, number of drawers, clearances, thick and thin sheets, slide thickness / length / height / clearance), a live table of the pieces to cut and Generate, which saves the list as a CSV (`Drawer Blocks - 2 drawers 760x350x540.csv`). Spec `docs/superpowers/specs/2026-11-13-drawer-blocks-design.md`, plan `docs/superpowers/plans/2026-11-13-drawer-blocks-high-level-plan.md` (all four tasks done).

- Rules: `core/drawer_rules.py` (standard library only; `generators/DrawerBlocks/skills/drawer-blocks-generator/scripts/d02_rules.py` is its exact copy, a test keeps them equal). The spreadsheet `Drawer calculations.xlsx` was checked and corrected, the corrections are listed in the spec (box depth minus facade and back, top and bottom as deep as the sides, drawer side height minus the thin bottom nailed under, facade height shares the full front, 0.5 mm clearance on each side of each slide). Sanity checks name the field at fault: slide height <= drawer side height, slide length <= box depth, no zero or negative size.
- Generator: `build_cutlist.py` (command line, last line `OK` or `FAILED: ...`), run by the normal runner and cache.
- The 3D check model of the example (`examples/Drawer Block - 2 drawers 760x350x540.step`, 21 named solids, not in git) was made by a throw-away cadquery script; cadquery is NOT a dependency of the app. A 3D output could become a generator later.
- The tests of the generic infrastructure of the Multiboard repo (`test_cache`, `test_jobs`, `test_runner`, `test_job_controller`, `test_save_flow`, stub generator) were not copied; `tests/test_gui_smoke.py` covers the whole path with the real generator. Bring them over when needed.
- `app/theme.py` got a table style (`pieceTable`, `pieceTotal`) on top of the Multiboard one; the save dialog has a CSV filter.

Names: app "Cutsheet Generator", folder/data `CutsheetGenerator`, env vars `CUTSHEET_CACHE_DIR` and `CUTSHEET_SETTINGS_DIR`, icon `app/assets/cutsheet.ico` (drawn by `tools/make_icon.py`: a slate tile with a board cut into pieces, one in the accent red), installer `installer/cutsheet.wxs` (WiX 5, per-user MSI, the launcher builds the venv at first launch), `python installer/build_msi.py` -> `installer/output/CutsheetGenerator-<VERSION>.msi`. The WiX UpgradeCode is its own GUID (never reuse the Multiboard one).

## Layout (as in the Multiboard Generator)

- `generators/` and `bundle_manifest.json`: the SOURCE of the generators, one folder per tab, each a skill-like folder of scripts with a command line. Editing a script changes the generator version and invalidates every cached result; run `python tools/sync_generators.py --update-manifest` after editing (a test checks it).
- `core/`: standard library only, never imports `app/`. `catalogue.py` (parts, parameters, command lines; it runs nothing), `params.py` (canonical values, so equal requests share one cache key and one output name), `runner.py`, `cache.py`, `jobs.py`.
- `app/`: the GUI; forms are generated from the catalogue (`param_form.py`), each screen remembers its last valid values (`settings.py`), tabs emit `generate_requested(part, params)`; `main_window.py` connects each new tab to `start_job` and `_set_busy`.

## Rules

- Tests: `.venv\Scripts\python -m pytest` from this folder. `pytest.ini` deselects `-m slow`.
- Change a rules module and its generator together, and keep a test that proves they agree.
- About and wait cursor: Help > About (`app/about.py`) shows the description and the version read from `VERSION`; the wait cursor is on the whole app while a generation runs. `tests/conftest.py` collects garbage between tests: keep it.
- Style: the look of the app is `app/theme.py` only; widgets keep names, texts and signals and the style sheet picks them up by class, object name and the `invalid` property. Keep it identical to the Multiboard Generator unless the user asks otherwise.
- Releases: semantic version in `VERSION`; a release is a commit "version X.Y.Z" and a tag `vX.Y.Z`, then the MSI. No release unless asked.
- Plans and implementation (the standard way of working, set by the user): for a feature of several steps, write the design spec (`docs/superpowers/specs/`) and get it approved, then a HIGH-LEVEL plan with a task list (`docs/superpowers/plans/`, approved by the user), then for each task in turn: detail that task in the plan file, execute it at once, run ONLY the targeted tests of that task, mark it done, go to the next. Commit and push only when the user asks.
