# Drawer Blocks Implementation Plan (high level)

> Way of working of this project: each task is detailed just before it is executed, tested with its own tests only, then marked done here.

**Goal:** the Drawer Blocks tab: a form for the block of drawers, a live table of the pieces to cut, and Generate saving the list as a CSV.

**Architecture:** rules in `core/drawer_rules.py` (standard library only); a bundled generator script writes the CSV (its rules file is an exact copy, a test keeps them equal); one catalogue part `drawer_blocks` goes through the normal runner, cache and save flow; the tab shows the table from the rules module directly.

**Tech Stack:** Python 3.14, PySide6, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-drawer-blocks-design.md`

## Global Constraints

- All dimensions in mm. Defaults: 760 x 350 x 540 available, box clearance 4, 2 drawers, drawer clearance 5, thick 18, thin 6, slide 12 x 500 x 35 high, slide clearance 0.5.
- Default result: box top/bottom 2 x 756 x 512, sides 2 x 310 x 512, back 756 x 346 (thin), drawer sides 4 x 500 x 141.5, front/back 4 x 658 x 141.5, bottoms 2 x 694 x 500 (thin), facades 2 x 756 x 165.5.
- `core/` imports nothing outside the standard library and never `app/`.

## Review Focus

- One drawer (N = 1) and many drawers (too many for the height): a clear error under the Drawers field, never a negative size.
- A slide higher than the drawer side, or longer than the box depth: error under that field.
- Thin or thick thickness so large that a width or depth becomes <= 0: error, not a crash.
- Equal requests written differently ("18cm", "180") share one cache key and one output name.
- The generator reports `FAILED: ...` (exit 1) on invalid arguments instead of writing a partial file.

## Tasks

- [x] **1. Rules** - `core/drawer_rules.py`: `Piece`, `DrawerError(param, message)`, `plan_drawer_block(...) -> list[Piece]`, `pieces_to_csv`. Tests `tests/test_drawer_rules.py`: default list, N = 1 and 3, every validation.
- [x] **2. Part and generator** - `Param`s and `drawer_blocks` Part in `core/catalogue.py` (check maps `DrawerError` to `ParamError`), `generators/DrawerBlocks/skills/drawer-blocks-generator/scripts/{build_cutlist.py,d02_rules.py}`, manifest. Tests: copy equal to core, catalogue names and canonical values, command line writes the CSV, `FAILED` on a bad request.
- [x] **3. Tab** - `app/drawer_blocks_tab.py` (form, live table of pieces, Reset, Generate), wired in `main_window.py` (`start_job`, `_set_busy`), form remembered in settings. Tests: table content, an invalid field disables Generate, Generate emits the part and params.
- [x] **4. End to end** - JobService + real generator + save of the CSV through the window; cache hit on the second run. Update CLAUDE.md, README and the spec state; regenerate the example STEP with the slide clearance.
