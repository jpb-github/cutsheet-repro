# Progress (Cutsheet Generator)

Last updated 2026-11-13. Read `CLAUDE.md` first (layout, rules, way of working), then this file.

## Where we are

- App (PySide6) cloned from the Multiboard Generator; version 0.1.0, not released. Repo: https://github.com/jpb-github/cutsheet-repro (master). Tests: `.venv\Scripts\python -m pytest` (183 pass).
- One tab, **Drawer Blocks**: grouped one-letter form on the left, merged list of pieces + hardware (pocket screws, pulls) top right, always-drawn perspective view of the closed block bottom right, help text and Reset / Refine / Cutsheet / Generate on the bottom row. Generate saves the list as a CSV through the normal generator/cache/save pipeline; Cutsheet writes the PDF (all eight cutsheet tasks done, nothing left in the plan).
- Rules (corrected from `Drawer calculations.xlsx`): `core/drawer_rules.py` (exact copy in `generators/DrawerBlocks/.../d02_rules.py`, a test keeps them equal; after editing run `python tools/sync_generators.py --update-manifest`). View: `core/drawer_view.py` + `app/block_view.py`.
- Specs and plans in `docs/superpowers/`: `specs/2026-11-13-drawer-blocks-design.md`, `specs/2026-11-13-cutsheet-design.md` (approved), `plans/2026-11-13-drawer-blocks-high-level-plan.md` (done), `plans/2026-11-13-cutsheet-high-level-plan.md`.

## Cutsheet plan (PDF with optimized layout)

- [x] 1. Grouped form (`Param.row`, `short`), View button removed, view always drawn
- [x] 2. Sheet size (single or per thickness, default 2400 x 1200), kerf 5, piece-fits-sheet check (`Param.when`, `sheet_for`)
- [x] 3. Guillotine packer `core/cutting.py` (single deterministic run, cut tree, `check_layout`)
- [x] 4. Search: multi-start, process pool (80 % of cores), 15 s default, Refine, never worse
- [x] 5. Cutsheet data `core/cutsheet.py` (labels, pocket screw positions, cut instructions)
- [x] 6. PDF writer `app/cutsheet_pdf.py` (Qt QPdfWriter, A4 landscape)
- [x] 7. Cutsheet and Refine buttons (Cutsheet where View was, left of Generate), background search, save, open PDF
- [x] 8. Finish (PDF looked at with real fonts, cut instruction lines shortened, docs updated)

Each task is detailed in its plan file just before it is executed (task 2 shows the level of detail), tests first, only that task's tests run, then marked done. Commit/push only when asked; no release unless asked.

## Decisions to remember

- Spreadsheet fixes: box depth = D - clearance - thick (facade) - thin (back); top/bottom as deep as the sides; drawer sides/front/back height minus the thin bottom (nailed under); facade height shares the full front; 0.5 mm clearance each side of each slide (drawer 2 mm narrower).
- Pocket screws: length from the sheet thickness (Kreg chart, fine thread for MDF; 18 mm -> 32 mm), count per joint = max(2, ceil(length / spacing) + 1), spacing 150; positions (i + 0.5) x length / n.
- Cutsheet: own guillotine packer (approach B), standard library only; pieces may rotate, no edge trim; cuts numbered by tree depth; no time-based tests (use `iterations=` and a seed); no GPU; PDF written with Qt; Refine continues from the best layout.
- The painter's order of the 3D view uses separating planes between boxes (sorting faces by their centre drew the wrong thing).

## Gotchas

- Offscreen Qt has no fonts: screenshots show text as boxes, layouts are still checkable.
- `examples/` (a throw-away STEP of the example block) and `.venv/` are git-ignored; the cadquery venv used for the STEP lives in the session scratchpad, cadquery is not an app dependency.
- WiX UpgradeCode of the installer is its own GUID; the installer has not been built or tested in this repo.
- A tab built in a test must be kept alive while its form is used (a temporary tab is garbage collected and its widgets deleted).
