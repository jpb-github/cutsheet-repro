# Drawer Blocks tab: design (approved 2026-11-13, with the slide height and the slide clearance added)

Goal of the first version: from the available space and a few parameters, list the wood pieces to cut (name, material, quantity, dimensions) for a block of drawers made of MDF. All dimensions in mm. No drawing, no nesting on sheets yet.

## Construction (as described by the user)

- Two kinds of MDF: THICK (default 18) for the outside box, the drawer sides, fronts and backs, and the facades; THIN (default 6) for the box back and the drawer bottoms.
- Outside box: two sides sandwiched between a top and a bottom (both span the full box width, so they cover the edges of the sides), and one thin back that overlays the rear edges of the four panels.
- Drawers: rectangular boxes joined by pocket screws; the front and the back are sandwiched between the two sides; the thin bottom is nailed under the sides, front and back (not recessed, so it adds its thickness to the drawer height and covers the outside of the drawer).
- Slides fit entirely outside the drawer (thickness 12 on each side, length 500), between the drawer and the box side.
- Facades: one thick panel per drawer, in front of the drawers and of the box; they cover the sides of the box. The facade thickness is the depth taken in front of the box.
- The AVAILABLE SPACE (W, H, D) is the total space the block must fit in, facades and box included.

## Parameters (defaults from `Drawer calculations.xlsx`)

| Name | Default | Note |
|---|---|---|
| Number of drawers N | 2 | 1 or more |
| Drawer clearance g | 5 | gap above and below every drawer and every facade (N + 1 gaps) |
| Available space W x H x D | 760 x 350 x 540 | |
| Box clearance c | 4 | total per dimension (about 2 on each side) |
| Thick, thin | 18, 6 | MDF thicknesses |
| Slide thickness s, length L | 12, 500 | |
| Slide height | 35 | must not exceed the drawer side height hs (checked) |
| Slide clearance sc | 0.5 | on each side of each slide (between the box and the slide, and between the slide and the drawer): 2 in total per drawer width |

Derived: box width Wb = W - c = 756, box height Hb = H - c = 346, depth available Db = D - c = 536.

## Pieces and formulas

| Piece | Qty | Length x width | Material |
|---|---|---|---|
| Box top / bottom | 2 | Wb x (Db - thick - thin) = 756 x 512 | thick |
| Box sides | 2 | (Hb - 2 thick) x (Db - thick - thin) = 310 x 512 | thick |
| Box back | 1 | Wb x Hb = 756 x 346 | thin |
| Drawer sides | 2N | L x hs = 500 x 141.5 | thick |
| Drawer front / back | 2N | (dw - 2 thick) x hs = 658 x 141.5 | thick |
| Drawer bottom | N | dw x L = 694 x 500 | thin |
| Facade | N | Wb x hf = 756 x 165.5 | thick |

with the drawer outside width dw = Wb - 2 thick - 2 (s + 2 sc) = 694, the drawer height hd = ((Hb - 2 thick) - g (N + 1)) / N = 147.5, the drawer side height hs = hd - thin = 141.5 (the bottom is under the sides), and the facade height hf = (Hb - g (N + 1)) / N = 165.5 (facades share the full front height with the same gaps).

The box side depth is the available depth minus the facade (thick) and the back (thin): the facade sits in front of the box, the back behind it.

## Corrections to the spreadsheet

1. Box depth: the back thickness was not deducted (sides 518 -> 512).
2. Box top and bottom were made as deep as the available depth, so the box would stick out in front of the facade (536 -> 512, the same as the sides; the user said to ignore the spreadsheet here).
3. Drawer sides, fronts and backs: the bottom is nailed under, so its thickness is taken from their height (147.5 -> 141.5).
4. Facade height was the drawer height (147.5); it is now the share of the whole front (165.5).
5. The slide clearance (0.5 on each side of each slide) narrows the drawer by 2 (696 -> 694, front/back 660 -> 658).
6. Kept as in the sheet: drawer side length (the slide length), facade width, the clearance of 4 as a total.

## Validation (errors shown under the field, the same way as the other forms)

- N >= 1, all lengths > 0, thicknesses within the sizes they must fit.
- Slide length L must not exceed the box depth (512) (the drawer front is flush with the box front).
- Sanity check: the slide height must not exceed the drawer side height hs (141.5 by default); the error is shown under the slide height field.
- Every computed dimension must be > 0 (drawer height, facade height, inside widths).

## Output and architecture

- The rules live in `core/drawer_rules.py` (standard library only: parameters -> list of Piece(name, material, qty, length, width, thickness)); the generator script `generators/DrawerBlocks/skills/drawer-blocks-generator/scripts/build_cutlist.py` has an exact copy (a test keeps them equal), like `grid_rules` / `g02_plan` in the Multiboard app.
- The catalogue gets a part `drawer_blocks` (tab `drawer_blocks`) whose generator writes `Drawer Blocks - NxWxHxD.csv` (one line per piece); Generate runs through the normal job pipeline, cache and save dialog.
- The tab shows the form and, live under it, the table of pieces (same rules module, no job needed) and the total count; Generate saves the CSV.

## Not in this version

Sheet layout/nesting and waste, grain, edge banding, hardware list (screws, nails, slides), the deeper top and bottom of the spreadsheet, drawings.

## Open points

- Hardware and sheet nesting are the likely next steps.
- Output format beyond CSV (a printable page) is not decided.
