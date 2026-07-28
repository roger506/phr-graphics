# Future improvements / known follow-ups

## Two-step spec commit (noted 2026-07-28)
The daily scheduled run commits each day's spec file in TWO commits:
1. a placeholder stub (literally "PLACEHOLDER_WILL_REPLACE" / "FILE_CONTENT_PLACEHOLDER"), then
2. a correction commit with the real inline-HTML content.

This is almost certainly a side effect of pushing the large (~6 KB) spec
content to GitHub through the Zapier GitHub action, which the scheduled
session must use (it cannot git push directly).

Impact:
- GitHub Actions: none (public repo = unlimited free minutes; the extra
  render cycle is free).
- Zapier: ~2 extra tasks/day (two GitHub write calls instead of one), on the
  order of ~60 extra tasks/month. This eats back the split-ledger savings.
- Model usage: negligible.

Status: HARMLESS. render.py now skips the placeholder cleanly and exits 0
(commit 6974200), so the stub commit no longer fails the workflow or emails
Roger. The two-commit habit itself remains.

Fix (down the road): get the run to write the full spec in a single commit
(e.g., stage the placeholder to a non-triggering path and only publish to
specs/ once, or find a single-call commit path through Zapier). Doing so
roughly halves the daily Zapier cost from ~4 tasks back to ~2.
