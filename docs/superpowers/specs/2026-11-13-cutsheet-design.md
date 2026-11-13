# Cutsheet (PDF) for the Drawer Blocks tab: design (implemented, all tasks done)

Builds on `2026-11-13-drawer-blocks-design.md` (the pieces, the pocket screws). All dimensions in mm.

## Intent

The cut list says what to cut; the cutsheet says HOW: which pieces go on which MDF sheet, where to cut and in which order, so that the least wood is bought and every cut is a clean cut from edge to edge. The output is a PDF to print and take to the saw (or to the store's panel saw for the largest sheets). The user chooses the tool for each cut, so the sheet does not depend on a saw type.

## Goals

- A PDF with: a summary page; one page per sheet with every piece drawn at scale, its label and dimensions, the cuts numbered in order, the kerf, the pocket screw marks; a page that draws each distinct piece large, with its dimensions and the positions of its pocket screws.
- Full cuts only: every cut crosses the whole rectangle it divides (guillotine layouts).
- Fewest sheets, then least waste. A result found in 15 s by default, using up to 80 % of the CPU cores; the user looks at it and can ask for more search (Refine), which never makes the result worse.
- Sheet size: one size for all thicknesses by default, one per thickness with a check box. Default 2400 x 1200 (the largest the user buys; smaller ones are typed in). Saw kerf, default 5.
- The form on the left groups dimensions on a line with one-letter labels; the 2D view of the block is always shown (no View button); the Cutsheet button is where View was, to the left of Generate.

## Non-goals and anti-goals

- No trim of the sheet edges, no grain direction (MDF has none, so every piece may be rotated by 90 degrees), no offcut inventory, no costs, no mixing of thicknesses on a sheet, no GPU (a branchy search over a few dozen rectangles gains nothing from one).
- Anti-goals: a cut that stops inside a piece; pieces that overlap a kerf; a PDF whose text is too small to read; a result that silently drops a piece.

## Approaches (chosen: B)

- A. A packing library (rectpack, greedypacker) with pieces enlarged by the kerf: a dependency for the installer, no cut order, guillotine guarantee unconfirmed. Rejected.
- B. Our own guillotine packer with multi-start search. Chosen: simple, standard library only, the cut tree gives the cut order directly, good for 10 to 30 pieces.
- C. Exact search over all cuts: optimal but explodes beyond about 15 different sizes. Rejected (a polish step may come later).

## Form (left side)

Grouped lines, a letter in front of each field, one "mm" at the end (typed units such as 76cm are still accepted and canonicalised to mm):

```
Space        W [760] H [350] D [540]
Clearance    Box [4]  Drawer [5]  Slide [0.5]
Drawers      N [2]
Thickness    Thick [18]  Thin [6]
Slide        T [12] L [500] H [35]
Sheet        L [2400] W [1200]   [ ] One size per thickness
               ticked: Thick sheet L W, Thin sheet L W (the single line is hidden)
Saw kerf     [5]
Screws       Spacing [150]
```

Letters: W width, H height, D depth, L length, T thickness; where a letter would collide the word is written. `Param` gets `row` (consecutive parameters with the same row share a line) and `short` (the letter). The error of a field shows under its line. New parameters: `sheet_length`, `sheet_width`, `per_thickness` (bool), `thick_sheet_length`, `thick_sheet_width`, `thin_sheet_length`, `thin_sheet_width`, `kerf`. A piece that cannot fit its sheet in either orientation is an error under the sheet field, naming the piece.

## Algorithm (core, standard library only)

1. Pieces: the cut list expanded to one rectangle per piece (a label per distinct size: A, B, C ...; numbered copies A1, A2), grouped by material (thick, thin), each group packed on its own sheets.
2. Packer: guillotine free-rectangle packing. A free rectangle F receives a piece in its corner; two cuts separate it (one across F, one across the strip that holds the piece); each cut costs the kerf; the rest become new free rectangles. No cut when the piece fills the dimension. Rotation allowed. Choice of the free rectangle (best short side, best long side, best area, worst area) and of the split (shorter or longer leftover, min or max area, horizontal or vertical first) are the parameters of a run; the order of the pieces is the other (sorted by area, long side, or perturbed at random).
3. Search: many runs with different choices and random orders from a seed; keep the best by (number of sheets, wasted area, number of cuts, minus the largest offcut). Run in a pool of worker processes (80 % of the cores, at least 1) until the time is out (15 s by default) or an iteration count is reached (tests, so results are reproducible). Refine continues from the best layout so far with new seeds and keeps the better one.
4. Result: for each sheet the tree of cuts. Cut order: by depth in the tree (all the first cuts of the sheet, then the cuts of the pieces they made), left to right, top to bottom; each cut carries the rectangle it divides, its direction and its distance from the edge of that rectangle (to the line, the blade on the waste side). A piece that is exactly a free rectangle needs no cut.
5. Pocket screws: positions along the joint edge i + 0.5 over n times the edge length (equal spacing, centred: for 141.5 and 2 screws, 35.4 and 106.1 from the end; for the 512 box joint 5 screws, the first 51.2 from the end and 102.4 apart), edges as in the hardware rules: both short ends of drawer fronts and backs, both long edges of box sides.

## PDF (Qt, QPdfWriter and QPainter in the app)

A4 landscape, vector, same rendering code for every page. Summary: the parameters, the sheets used, waste per sheet, the list of pieces with labels, the hardware. Sheet pages: the sheet outline with its size, each piece (label, L x W, rotated or not), cut lines with a number in a circle and the kerf drawn to scale where it is visible, an instruction list of the cuts under the drawing. Piece pages: each distinct piece at a scale that fills a cell, dimensions on two sides, pocket screw marks with their distance from the end.

## Flow in the app

- Cutsheet: runs the search in the background (the status bar shows the time and the best sheet count so far, Cancel keeps the best so far), then asks where to save the PDF (default name `<list name> cutsheet.pdf`, folder remembered), writes it and opens it in the default PDF viewer.
- Refine (next to Cutsheet, enabled once a result exists and the form has not changed): another 15 s from the current best; rewrites the same PDF only when the result is better, and says so in the status bar. If the file is open and locked the error is reported and another name is offered.
- Not cached with the job cache: the search is time-based, so a result is not a pure function of the form.

## Decisions I made (open to correction)

Rotation allowed; no edge trim; cut numbering by tree depth; A4 landscape; pocket screws equally spaced, centred; Refine rewrites the same file; the new parameters are part of the form's cache key for the CSV (extra cache misses when only a sheet size changes, accepted).

## Left to the builder

Exact heuristic list and scoring weights, the layout of the pages, fonts and sizes, scale choices, how progress is reported between processes, the file naming.

## Acceptance

- Default form: one thick sheet and one thin sheet, every piece placed once, no overlap, kerf respected, every cut full width of its rectangle.
- 1200 x 1200 sheets: the thick pieces need two sheets; a piece larger than the sheet is refused with a message under the sheet field.
- Same seed and iteration count: same result; Refine never returns a worse one.
- The PDF has the summary, one page per sheet and the piece pages, readable at A4.
