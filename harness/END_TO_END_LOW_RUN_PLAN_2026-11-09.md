# End-to-end LOW run plan — popaurmaa.com harness (Finding 3)
**Date:** November 9–10, 2026
**Status:** PLAN READY — NO CANDIDATE FOUND YET. Nothing has been committed, deployed, or changed. The founder approves the candidate before any live change.

## 1. The candidate search — result: NO genuine LOW candidate exists
Every text-bearing file of the live site was read in full (Nov 9–10, 2026) and every user-visible string was checked for a genuine typo, outdated wording, or dead-end copy:
- `index.html` (13,782 bytes, all sections: hero, about, services, ventures, media, contact, footer, JSON-LD, meta/OG tags) — copy is clean. Checked twice, word by word.
- `site-config.js` — contact email correct; three venture descriptions clean; link texts match their destinations.
- `script.js` — all user-visible strings (form labels, options, button, fineprint) clean; the footer year is dynamic (`new Date().getFullYear()`).
- The three redirect stubs (`about-founder`, two `/f/` stubs) — clean, correct targets and canonicals.
- `README.md` — repo file, not live-site copy; not a candidate for a live change.

Borderline items considered and rejected as candidates (not genuine errors):
- "sound checks and engagement logistics" (about section) — "engagement" is a booked performance; the phrasing is legitimate, not a typo.
- "Select play to watch." (media section) — terse but intentional.
- "accommodation coordination" — "accommodation" is spelled correctly.
- The `?v=20261028-popaone` cache-buster strings — version markers, not displayed copy.

**A comment-only change is NOT a real change and is not proposed as a substitute.** The honest alternatives are: (a) hold the end-to-end run until the founder names a real LOW change he wants, or (b) run it the next time a real typo or wording fix surfaces. This plan is complete and ready for either.

## 2. Candidate criteria (for the founder, or a future run)
A valid LOW candidate must satisfy ALL of these:
1. It touches only existing visible text in `index.html` (or a stub) — no links, no prices, no metadata (canonical/OG/JSON-LD/title), no contact info, no legal text, no new sections, no asset changes.
2. It is plainly an improvement: a typo fix, a corrected fact, or wording the founder has asked to change.
3. The old and new text are both quoted verbatim in the run record, so the founder can approve the exact change.
4. It is small: a sentence or less, one place in the file.

## 3. The run plan (execute when a candidate is approved)
Assumes: the v1.1 workflow is NOT yet installed (install on hold pending the GitHub App write-access fix), so this run is manual — spec first, isolated implementation, script, commit via the GitHub connector (fresh approval card per write), post-deploy verify, record. When the workflow IS installed, the same steps run through a PR instead of a direct commit; the checks are identical.

### Step 0 — Architect spec (before any implementation)
Write the candidate into this plan: the exact old text, the exact new text, the file and line, the tier (LOW), and the acceptance criteria (the new text is live, all checks pass, nothing else changed). Founder approves the candidate (his words, dated).

### Step 1 — Implement in isolation
Work in a local copy of the repo at HEAD `5a887858` (or the current HEAD — re-verify it first with `list_commits`). Make ONLY the approved change. Produce the diff:
```
git diff HEAD -- . > change.diff
```
Confirm the diff contains only the approved change (read it line by line).

### Step 2 — Run the checks (v1.1 script)
```
python3 harness/checks/check_popaurmaa_v1.1.py \
  --html <copy>/index.html --repo-dir <copy> \
  --diff-file change.diff \
  --base-sha <base-sha> --head-sha <new-head-sha> \
  | tee harness-run-low-YYYYMMDD.txt
```
Expected: exit 0; `scope_guard` reports LOW; `approval` reports PASS ("LOW change — no founder approval required"); every mandatory check PASS. If anything FAILs, stop, fix the change (never the script), re-run. Save the output with the run record.

### Step 3 — Commit
Commit message (states the tier and the check result, per the spec):
```
LOW: <one-line description of the fix> (harness v1.1: 8 PASS, 0 FAIL)
```
Commit via the GitHub connector (fresh approval card). Record the new commit SHA.

### Step 4 — Post-deploy verify
After GitHub Pages deploys (allow ~2 minutes), run:
```
python3 harness/checks/check_popaurmaa_v1.1.py \
  --expect "<the new text, verbatim>" --head-sha <new-commit-sha>
```
Expected: exit 0; `post_deploy_verify` PASS (marker present in live HTML). Also re-fetch the live page and confirm the byte change is exactly the approved one (diff live HTML against the previous HEAD).

### Step 5 — Record
Write the run record next to this plan: candidate (old/new text), tier, check output file, commit SHA, post-deploy output, and the founder's approval words + date. Update the spec's §11 file list if the run changes anything about the harness itself (it should not).

### Rollback (if the post-deploy verify fails)
```
git revert <new-commit-sha>
```
via the GitHub connector (fresh approval card), then re-run the script to confirm the live page is back to the previous state. The exact revert command is printed by the script's `post_deploy_verify` output.

## 4. What this run will prove (and what it will not)
It will prove: the full procedure works end to end on a real change — spec → isolated implementation → checks → commit → live verify → record — with the v1.1 script and exit codes. It will NOT prove: CI enforcement (the workflow is not installed yet), branch protection (not installed yet), or the MEDIUM/HIGH paths (this run is LOW by design). Those need their own first runs when a MEDIUM or HIGH change arises.
