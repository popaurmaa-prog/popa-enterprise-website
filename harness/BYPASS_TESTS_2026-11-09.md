# Bypass + approval test log — harness v1.1 (Findings 1 and 4)
**Date:** November 9–10, 2026
**Method:** synthetic git repos and file copies under `_test-scratch/` (never the live repo or the live site, except the scripts' own read-only fetches of public URLs). Drivers kept in `_test-scratch/`: `test_finding1.py`, `test_finding4.py`. Bulky synthetic repo copies were removed after the runs; the drivers and the `.diff` files they used are kept as the reproducible evidence.
**Result: Finding 1: 18/18 passed. Finding 4: 8/8 passed.**

## Evidence labels
- **VERIFIED** — directly observed in a dated record. **PROPOSED** — appears in a proposal only.

## Finding 1 — bypass scenarios (a)–(e)

| Test | Scenario | Result | Evidence |
|---|---|---|---|
| BYP-A0 | Control: untampered v1.1 script on a page with the JSON-LD block removed | PASS | Exits 1 (`required_tags` FAIL). The break is real and detected. |
| BYP-A1 | Tampered script (required-tags check neutered) on the same broken page | PASS | Tampered copy exits 0 — the threat is real: a weakened script would green-light a bad change. |
| BYP-A2 | Workflow guard: PR modifies `harness/checks/check_popaurmaa_v1.1.py` | PASS | `git diff --name-only <base> <head> -- harness/checks/ .github/workflows/` lists the script → the v1.1 guard step fails the job with "harness files changed". |
| BYP-A3 | Script run from the base branch | PASS | `git show <base>:harness/checks/check_popaurmaa_v1.1.py` returns the untampered script (no "tampered" marker, enforcement header intact) even when the working copy is tampered. |
| BYP-A4 | Base script on the broken page | PASS | Exits 1 (`required_tags` FAIL) — the base copy correctly rejects the break. |
| BYP-B-workflow-only | PR touches only `.github/workflows/harness.yml` | PASS | v1.0 trigger paths match=False (job would NOT run); v1.1 match=True. |
| BYP-B-asset-only | PR touches only `assets/new-poster.jpg` | PASS | v1.0=False; v1.1=True (via `assets/**`). |
| BYP-B-zip-only | PR touches only `site-bundle.zip` | PASS | v1.0=False; v1.1=True (via `**.zip`). |
| BYP-B-paths | v1.1 trigger paths contain the fixes | PASS | `.github/workflows/**`, `assets/**`, `**.zip` all present in both `pull_request` and `push` paths. |
| BYP-C | Direct push to `main` | PASS (design verification) | v1.1 workflow runs on `push` to `main` (detection after the fact). ONLY branch protection blocks a direct push; protection is NOT installed (pending the GitHub App write-access fix). Verdict: BYPASS POSSIBLE without protection, BLOCKED with it. |
| BYP-D1 | Broken relative link (`assets/missing-poster.jpg`) under v1.0 | PASS | v1.0 exits 0 — the gap was real (no relative-asset check). |
| BYP-D2 | Same broken link under v1.1 | PASS | v1.1 exits 1 with `relative_assets` FAIL naming the missing file. |
| BYP-E---skip | `--skip` flag | PASS | Exit 3 (argparse rejects it; usage errors exit 3). |
| BYP-E---disable | `--disable` flag | PASS | Exit 3. |
| BYP-E---ignore | `--ignore` flag | PASS | Exit 3. |
| BYP-E-flags | No skip/disable/ignore flag defined | PASS | The words appear only in the docstring prohibition. |
| BYP-E-wf10 | v1.0 workflow flaw (static) | PASS | The v1.0 draft contains neither `--diff` nor `--html` — it checked the live site, not the PR's change. |
| BYP-E-wf11 | v1.1 workflow checks the PR's content | PASS | The v1.1 draft passes `--diff-file` and `--html`. |

## Finding 4 — exit codes and approval outcomes

| Test | Scenario | Result | Evidence |
|---|---|---|---|
| F4-1 | HIGH change, no approval record | PASS | Exit 2; `approval` AWAITING_APPROVAL; `RESULT: AWAITING_APPROVAL`. |
| F4-2 | HIGH change + valid approval record | PASS | Exit 0; `approval` PASS ("HIGH change APPROVED — record verified, tier HIGH, diff hash matches, approved 2026-11-09"). |
| F4-3 | Change amended after approval (stale record) | PASS | Exit 2; reason "diff-sha256 mismatch". |
| F4-4 | HIGH change + security FAIL + valid approval | PASS | Exit 1; `RESULT: FAIL`. Security failure takes precedence — the approval record cannot override a failed check. |
| F4-5a | LOW change | PASS | Exit 0; `scope_guard` LOW; `approval` PASS ("no founder approval required"). |
| F4-5b | MEDIUM change | PASS | Exit 0; `scope_guard` MEDIUM; `approval` NOT RUN ("second readback is a manual step"). |
| F4-6a | `--diff` + `--diff-file` together | PASS | Exit 3 (usage error). |
| F4-6b | `--skip` (unknown flag) | PASS | Exit 3 ("unrecognized arguments"). |

Approval-record test setup (all synthetic): a scratch git repo at the v1.1 HEAD copy; the HIGH change was a `<p>Price: $99</p>` line added to `index.html`; the record was `harness/APPROVAL-20261109-<shortsha>.md` with the exact `diff-sha256` of `git diff <base> <head> -- . ':!harness/APPROVAL-*'`, the founder-approval words, and the date 2026-11-09; the record was committed as a separate commit on top of the change commit, and the script was run with `--head-sha` of the record commit (ancestry verified).

## Test-debugging notes (honest record)
Three defects were found in the TEST drivers during these runs — none in the implementation:
1. `test_finding4.py` called its helper with a stale extra argument (`script_run()` TypeError). Fixed the driver; the script was untouched.
2. F4-2's assertion checked for the string `AWAITING_APPROVAL` anywhere before `RESULT`, but the summary counts line itself contains "0 AWAITING_APPROVAL". The assertion was narrowed to the approval line itself; the script's output was correct all along (re-verified by a manual re-run: exit 0, approval PASS).
3. BYP-A1's first tamper (broken canonical) also tripped `metadata_consistency`, so the tampered script still exited 1 — the test break was not isolated to one check. The break was changed to a removed JSON-LD block (caught only by `required_tags`), with a control run (BYP-A0) proving the untampered script fails it. The implementation was untouched.
The implementation (script v1.1, workflow draft v1.1) was never edited to make a test pass.
