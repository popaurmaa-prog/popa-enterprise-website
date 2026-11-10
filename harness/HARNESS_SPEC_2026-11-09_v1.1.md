# Harness Spec — popaurmaa.com (v1.1)
**Funding All Ventures Business · harness pilot**
**Date:** November 9–10, 2026
**Authorized:** Founder, Nov 9, 2026, 18:15 CST (direct tap "Pilot the harness on popaurmaa.com"); v1.1 revisions authorized by the founder's review of Nov 9, 2026, ~18:31 CST (status CONDITIONAL PASS; four findings to resolve before production-ready)
**Target:** popaurmaa.com only — single-page static site, GitHub Pages, repo `popaurmaa-prog/popa-enterprise-website`, branch `main`
**Status:** v1.1 INSTALLED via founder-approved PR (approved Nov 9, 2026, 18:54 CST — "Yes, install v1.1 once access is fixed"). The workflow is live at `.github/workflows/harness.yml`; branch protection requiring the harness job is enabled after the merge. The Nov 9, ~18:30 CST install attempt failed with GitHub 403 (the App lacked write access); access was fixed Nov 9, 2026, and the install branch was created successfully. The v1.0 pilot record and evidence snapshots stay in the workspace (see §11).

## What changed in v1.1 (vs v1.0)
- **Finding 1 (bypass hardening):** the workflow runs the script from the base branch and fails the job if the PR touches harness/checks/ or .github/workflows/; trigger paths now include `.github/workflows/**`, `assets/**`, `**.zip`; the workflow checks the PR's content (`--html` + `--diff-file`), not the live site. All five bypass scenarios were tested (spec §10).
- **Finding 2 (asset coverage):** the script now checks relative image/video/poster/script/stylesheet/file URLs (local existence + live fetch) and scans the .zip bundle's TEXT contents under hard limits. CSS `url(...)` references are collected too.
- **Finding 3 (end-to-end LOW run):** no genuine LOW candidate was found in the live page copy (searched Nov 9–10, 2026; see `END_TO_END_LOW_RUN_PLAN_2026-11-09.md`). The run plan is complete and ready for the first real LOW change; no comment-only change was proposed as a substitute.
- **Finding 4 (HIGH approval mechanism):** a failed security check and a HIGH change awaiting approval are now distinct outcomes — exit 1 FAILED vs exit 2 AWAITING_APPROVAL — with a verifiable approval record (`harness/APPROVAL-*.md`, spec §7).

## Evidence labels used in this spec
- **VERIFIED** — directly observed in a dated record (file, live check, tool output).
- **FOUNDER-CONFIRMED** — the founder's direct words, dated.
- **PROPOSED** — appears in a proposal, handoff, or draft only.
- **UNVERIFIED** — could not be confirmed; the spec names what would verify it.

## 1. What the harness is
A small, explicit enforcement layer for changes to popaurmaa.com, adapted from the Anthropic/Christina "harness" idea in Popâ One's Nov 9 proposal: separate the architect from the engineer, make verification mandatory, and classify changes by risk. It does **not** adopt Scion and does not replace Git.

The harness has four parts:
1. **This spec** — tiers, roles, procedure, and what counts as a pass.
2. **The check script** — `checks/check_popaurmaa_v1.1.py` (Python standard library only, no new dependencies). It fetches the live page (or checks a local copy), checks required tags and metadata, resolves internal anchors, checks external links, checks relative assets, scans changed files for secret patterns (including the .zip bundle's text contents), classifies diffs, verifies approval records, and verifies a deploy after the fact.
3. **The approval record** — `harness/APPROVAL-*.md` (§7), a verifiable record that a HIGH change was founder-approved. The script verifies it; it does not trust it.
4. **The written record** — every run's output is saved with the change it belongs to. Until the workflow draft is approved and installed, the record is the enforcement.

## 2. Roles — architect / engineer separation
| Role | Who | Does | Does not do |
|---|---|---|---|
| **Architect / Coordinator** | Popâ One (or the founder) | Writes the requirements and acceptance criteria FIRST, in a spec file, before any implementation. Defines the risk tier. | Does not implement. Does not approve its own spec as "done" — completion is the script output plus live verification. |
| **Engineer / Implementer** | Popâ 2 | Implements the change in an isolated copy (a local copy or a branch). Runs the check script. Records the output. | Never approves its own work. Never edits the check script to make a failing check pass. Never disables a check. |
| **Verifier** | The check script, plus a second reader (MEDIUM) or the founder (HIGH) | Produces the PASS/FAIL evidence. A second human reader re-reads a MEDIUM change after checks pass, before any commit. The founder approves HIGH changes; the approval is recorded in a verifiable file (§7). | The verifier does not decide the tier — the tier comes from the diff (scope guard) and the table in §3. The script cannot verify that the founder actually typed the approval words — that trust comes from the approval happening in the founder's own words in chat (§7). |

## 3. Risk tiers (decided — apply them, do not redesign)
| Tier | What it covers (popaurmaa.com) | What happens |
|---|---|---|
| **LOW** | Text-only corrections to existing copy — no links, prices, metadata, contact info, or legal text. Example: fixing a typo in a paragraph. | May proceed after all checks pass. No second reader required. No approval record required. |
| **MEDIUM** | Link/URL changes; metadata changes (canonical, OG tags, JSON-LD, title, description); new anchor sections; changes to `site-config.js` (it holds the contact email and venture links); changes to relative assets (images, video, posters, stylesheets). | Needs an independent second readback (another agent) after checks pass, before any commit. The readback is a manual step the script cannot verify — it is recorded in the PR. |
| **HIGH** | Prices; legal text; contact info (including the contact email and the contact form); redirects (meta-refresh stubs, canonicals on stubs, CNAME); the chat widget (tawk.to); brand identity (page title, header brand, emblem). | Mandatory founder approval — unchanged from standing rules. The approval is recorded in a verifiable file (§7). A HIGH change with a valid approval record may proceed (exit 0, APPROVED). A HIGH change without one is AWAITING_APPROVAL (exit 2) — it still blocks merging, but for a different reason than a failed check. |

**The classifier cannot override a failed check at any tier. A failed check stays failed. An approval record cannot override a failed check either** — a HIGH change with a valid approval record but a failing security check still exits 1 (FAILED) and does not proceed. (Tested: Finding 4 test F4-4.)

## 4. Procedure (one change at a time)
1. **Architect writes the spec first.** Requirements, acceptance criteria, tier. No implementation before this exists.
2. **Engineer implements in isolation.** Work in a local copy or a branch. Never edit the live site directly; never edit `main` in place.
3. **Run the checks.** `python3 checks/check_popaurmaa_v1.1.py --html index.html --repo-dir <copy> --diff-file <change.diff> --base-sha <base> --head-sha <head>`. The script exits 0 (PASS/APPROVED), 1 (FAILED), 2 (AWAITING_APPROVAL), or 3 (usage error) and prints a per-check PASS/FAIL/NOT RUN/AWAITING_APPROVAL report. Save the output with the change. The diff file is produced with the canonical command (spec §7): `git diff <base> <head> -- . ':!harness/APPROVAL-*'`.
4. **Classify.** The scope guard reports LOW / MEDIUM / HIGH from the diff itself.
   - LOW + all checks PASS → proceed to step 5.
   - MEDIUM + all checks PASS → independent second readback (record it in the PR), then step 5.
   - HIGH + all checks PASS + valid approval record → step 5.
   - HIGH + all checks PASS + no valid approval record → exit 2. Obtain founder approval, add the approval record (§7), re-run from step 3.
   - Any FAIL → stop. Fix the change, re-run. Do not edit the script.
5. **Commit via the GitHub connector (once branch protection is installed, via a PR).** Each write shows a fresh approval card. Commit message states the tier and the check result. Until branch protection is installed, a direct commit to `main` is possible — that is why the install is not complete without it (spec §9).
6. **Post-deploy verify.** Re-fetch the live page (`--expect "<marker>" --head-sha <sha>`). Confirm the change is present and the required tags still pass. Record the output.
7. **Rollback if the verify fails.** `git revert <sha>` via the GitHub connector (fresh approval card), then re-run the script to confirm the live page is back. The exact revert command is printed by the script.

## 5. What counts as a pass
- Every mandatory check reports PASS: `live_http`, `required_tags`, `metadata_consistency`, `internal_anchors`, `external_links`, `relative_assets`, `secret_scan`, `redirect_stubs`.
- `scope_guard` must report a tier (LOW/MEDIUM/HIGH). It reports NOT RUN only when no diff was supplied — which means no change is being classified, so no change may proceed on that run.
- `approval` must report PASS (LOW: no approval required; HIGH: valid record verified) or NOT RUN (MEDIUM: the second readback is manual; no change supplied: nothing to approve). AWAITING_APPROVAL means a HIGH change has no valid record.
- `post_deploy_verify` reports NOT RUN until a deploy has happened; after a deploy it must report PASS.
- Exit code 0 (PASS/APPROVED). Exit code 1 (FAILED) blocks the change. Exit code 2 (AWAITING_APPROVAL) blocks merging until an approval record is added. Exit code 3 is a usage error — fix the invocation, do not proceed.

## 6. What the checks actually do (and their known limits)
- **Live fetch:** HTTP 200 for `https://popaurmaa.com/`. A fetch failure is a FAIL, not a pass. In `--html` mode the live fetch is skipped (the file under review is the PR's copy) and `live_http` reports the local file read instead.
- **Required tags:** canonical must equal `https://popaurmaa.com/`; all 5 OG tags present with the expected values; JSON-LD must parse, be an `Organization`, and contain no `sameAs`.
- **Metadata consistency:** `<title>`, canonical, and `og:url` must agree.
- **Internal anchors:** every `href="#…"` must resolve to an `id` on the page (11 anchors at baseline).
- **External links:** every absolute URL in `index.html`, plus the venture URLs rendered from `site-config.js`, plus absolute `url(...)` references from the repo's `.css` files (v1.1: the Google Fonts import in `styles.css` was invisible to v1.0 — the v1.1 baseline checks 15 URLs, not 14) must return HTTP 200. **Known behaviour (VERIFIED Nov 9, 2026):** Shopify returns 403 and Facebook returns 400 to bare-script requests while serving the same URLs to browsers. The script therefore sends full browser headers and retries a 400/403 once with navigation headers before failing. A genuinely dead link still fails (404, DNS error, timeout). This retry is documented in the script; it is not a way to hide a dead link.
- **Relative assets (v1.1, Finding 2):** every relative image / video / poster / script / stylesheet / local-file URL on the page — `img src`, `source src`, `video src` and `poster`, `script src`, `link href`, `srcset` entries, and relative `url(...)` references in `.css` files — must exist in the repo checkout. When the page under review IS the live page, each asset is also fetched from the live site and must return HTTP 200. In `--html` mode the live-fetch half is skipped on purpose: the live site cannot have assets that only exist in the PR yet. The skip is stated in the check detail, never silent. A relative path that escapes the repo root (`..`) is a FAIL. Baseline v1.1: 10 relative assets, all present locally and all live-fetched OK.
- **Secret scan:** TruffleHog-style patterns over text files (`.html`, `.js`, `.css`, `.xml`, `.txt`, `.md`) plus the entry *names* inside the repo's `.zip` bundle, plus — v1.1 (Finding 2) — the *contents* of the bundle's text files, read under hard limits (see below). Allowlist (hardcoded, with reasons): the GA4 measurement ID `G-RHE021T26E` and the tawk.to widget ID — public identifiers meant to appear in client-side code, not credentials. The allowlist cannot be extended from the command line. Binary files are counted as skipped in the check detail, not hidden. **ZIP limits (VERIFIED against the real bundle, Nov 9, 2026: 12 entries / 17,108,736 uncompressed bytes / largest single file 10,649,740 bytes):** max 500 entries; max 100,000,000 total uncompressed bytes; max 25,000,000 bytes per file. Unsafe entries — absolute paths, `..` traversal, symlinks — are a FAIL. A limit breach is a FAIL with the reason. Nothing from the zip is executed; entries are read into memory one at a time and never extracted to disk. Baseline v1.1: 11 repo text files scanned, 7 binary skipped (counted); zip 12 entries, 5 text scanned, 7 binary skipped, no suspicious names.
- **Redirect stubs:** the three stubs (`about-founder`, the two `/f/` stubs) must point at their matching homepage sections with matching canonicals.
- **Scope guard:** reads the diff's added/removed lines and changed file paths and flags price, legal, contact, redirect, chat-widget, and brand patterns (→ HIGH) and metadata/link/section patterns (→ MEDIUM). Any change to `site-config.js` is at least MEDIUM, because it holds the contact email and venture links. A diff touching `harness/checks/` or `.github/workflows/` is flagged in the detail — the workflow guard rejects it (spec §10). v1.1 accepts a unified diff file (`--diff-file`, multi-file, what CI passes) as well as a single file pair (`--diff`, local use). The guard reports the tier; it does NOT fail on HIGH — the blocking for HIGH lives in the `approval` check.
- **Approval (v1.1, Finding 4):** see §7.
- **Post-deploy verify:** re-fetches live HTML, confirms the expected marker is present, and prints the exact `git revert` command for the HEAD SHA.

## 7. HIGH approval records (v1.1, Finding 4)
A HIGH-tier change may proceed only with a valid approval record. The record is a file in the PR so it is reviewable; the script verifies it; it does not trust it.

### 7.1 Record format
File: `harness/APPROVAL-<YYYYMMDD>-<shortsha>.md` where `<shortsha>` is the first 7 characters of the change commit's SHA. Contents — machine-readable `key: value` lines (`#` lines are comments):
```
# Harness approval record — HIGH-tier change
tier: HIGH
change-description: <one line, what the change does>
base-sha: <40-hex SHA of the base commit>
head-sha: <40-hex SHA of the change commit the approval covers>
diff-sha256: <sha256 of the canonical diff, see 7.2>
founder-approval-words: "<the founder's exact words>"
approved-date: <YYYY-MM-DD>
recorded-by: <name or agent>
```
All keys except `recorded-by` are required. `founder-approval-words` must be the founder's exact words as he said them in chat (or tapped); the agent that received them records them verbatim.

### 7.2 The canonical diff (the hash binds the record to the exact change)
Both the author and the workflow compute the diff with this exact command:
```
git diff <base-sha> <head-sha> -- . ':!harness/APPROVAL-*'
```
and hash its bytes with SHA-256. The pathspec excludes approval records themselves, so adding the record does not change the change's hash. If the change is amended after approval, the hash no longer matches and the record is invalid — the author must obtain a fresh approval for the amended change.

### 7.3 How the author creates a record (exact steps)
1. Make the HIGH change and commit it. Note the commit SHA (`head-sha`) and the base SHA.
2. Compute the diff hash: `git diff <base-sha> <head-sha> -- . ':!harness/APPROVAL-*' | sha256sum`.
3. Obtain the founder's approval in his own words (chat or option tap). Record the exact words and the date.
4. Write `harness/APPROVAL-<YYYYMMDD>-<shortsha>.md` with the fields above and commit it as a separate commit on top of the change commit.
5. Push. The workflow re-verifies the record (7.4). Do not amend the change commit after step 4 — an amend creates a new commit, the old one stops being an ancestor, and the record becomes invalid.

### 7.4 How the script verifies a record
For each `harness/APPROVAL-*.md` found (in `--approval-dir`, default `<repo-dir>/harness`), the script checks, in order:
1. All required keys are present and `tier` is `HIGH`.
2. `base-sha` and `head-sha` are 40-hex SHAs; `approved-date` is a real `YYYY-MM-DD` date; `founder-approval-words` is non-empty.
3. `diff-sha256` equals the SHA-256 of the diff under review (the `--diff-file` bytes, or the generated unified diff for `--diff`). A mismatch means the change was amended after approval, or the record covers a different change.
4. Ancestry (when git is available and `--head-sha` is given): the record's `head-sha` must be an ancestor of (or equal to) the HEAD under review (`git merge-base --is-ancestor`). This rejects a record whose change was rewritten after approval. If git is unavailable, this step is skipped and the detail says so — the hash match (step 3) still binds the record to the exact change content.
A record passing all applicable checks → `approval` PASS ("HIGH change APPROVED"). No valid record → `approval` AWAITING_APPROVAL (exit 2).

### 7.5 What the mechanism does and does not prove
It proves: an approval record exists, is well-formed, matches the exact change content (diff hash), and covers a commit that is an ancestor of the HEAD under review. It does NOT prove the founder actually typed the approval words — the words in the file are only as trustworthy as the PR process and branch protection that keep the file from being forged by the change author. The trust chain is: the founder's words arrive in chat → the receiving agent records them verbatim → the record is reviewable in the PR → branch protection prevents merging without a passing harness job. If the words were fabricated, the script cannot detect it; the founder's review of the PR is the backstop. This limit is stated here deliberately, not hidden.

## 8. What the harness does NOT cover
- **Any property without source control.** ChatGPT Sites (rudetymz.com, popaone.com), LearnWorlds (Cataloghaus), and Shopify have no repo, no branches, and no place for these checks to run. The harness is popaurmaa.com only. (VERIFIED by the Stage 1 audit, Nov 9, 2026.)
- **Dependency / vulnerability scanning.** The site has no package manager and no dependencies to scan. Semgrep/Trivy-style checks do not apply to a static single-page site with no build step. The reference design's tool list is aspirational for this stack; the checks implemented are the ones that apply.
- **JavaScript / CSS syntax validity.** The script does not parse `script.js`, `site-config.js`, or `styles.css` for syntax errors. A change that breaks JS or CSS syntax would pass the harness and break the live site. (Named as a remaining gap, Finding 1d.)
- **Visual / layout regression.** No screenshot or layout comparison is implemented.
- **Performance or accessibility auditing.** Not implemented; no baseline exists for either.
- **Content correctness beyond the patterns.** The script checks that tags, links, and metadata are present and consistent. It cannot judge whether copy is accurate, on-brand, or legally sound — that is the architect's and (for HIGH) the founder's job.
- **The MEDIUM second readback.** The script reports it as NOT RUN and cannot verify a human re-read it. The readback is recorded in the PR; the workflow cannot enforce it.
- **Server-side enforcement.** See §9.

## 9. Enforcement — what it is and is not (honest statement)
**What it is:** a deterministic script plus a written record, plus — once installed — a CI job that runs the script from the base branch and a branch-protection rule that requires the job to pass. The script cannot be skipped from the procedure, has no disable flags, and its output is saved with every change. The tier rules are written here, not remembered.
**What it is not (yet):** a server-side gate until branch protection is enabled. The workflow is installed by this PR (`.github/workflows/harness.yml`); branch protection requiring the `harness` job to pass before merge is enabled separately after the merge — until then, a direct push to `main` can still land (spec §10c). The Nov 9, ~18:30 CST install attempt failed with GitHub 403 (the App lacked write access); write access was fixed Nov 9, 2026.
**Until then:** a change that skips the script is a procedure violation, detectable only because its record is missing. The record is the enforcement.
**Installed by this PR:** `.github/CODEOWNERS` requiring the repo owner's review for changes to `harness/` and `.github/` — a human review gate on the enforcement files themselves. Owner login `popaurmaa-prog` (VERIFIED from the repo's commit author). It binds only once branch protection requires code-owner review; CODEOWNERS alone only requests the review.

## 10. Bypass scenarios tested (v1.1, Finding 1)
All scenarios were tested Nov 9–10, 2026 with synthetic repos and diffs (never against the live repo). Full log: `BYPASS_TESTS_2026-11-09.md`. Test drivers kept under `_test-scratch/` (`test_finding1.py`, `test_finding4.py`).

| # | Scenario | Verdict | Evidence / fix |
|---|---|---|---|
| (a) | A PR modifies `harness/checks/check_popaurmaa_v1.1.py` itself to weaken a check | **BYPASS BLOCKED** (by design) | Threat proven real: a tampered copy of the script (required-tags check neutered) exits 0 on a page with the JSON-LD block removed, while the untampered script exits 1 (test BYP-A0/A1). Fix (two layers): the workflow runs the script from the BASE branch (`git show <base>:...`), so a tampered PR script never executes (BYP-A3); and a guard step fails the job if the PR modifies `harness/checks/` or `.github/workflows/` when those files exist in the base (BYP-A2). Script/workflow changes need a separate founder-reviewed PR merged by admin bypass. The install PR is the one exception (files not yet in base) and is allowed with a warning. |
| (b) | A PR modifies only `.github/workflows/harness.yml` | **BYPASS BLOCKED** (by fix) | The v1.0 draft's trigger paths did not include `.github/workflows/**`, so the harness job would not have run (verified by path matching: v1.0 triggers=False). v1.1 adds `.github/workflows/**`, `assets/**`, and `**.zip` to both `pull_request` and `push` paths (BYP-B-*). A workflow-only, asset-only, or zip-only change now triggers the job. Combined with the (a) guard, a workflow change fails the job rather than neutering it. |
| (c) | A direct push to `main` | **BYPASS POSSIBLE without branch protection; BLOCKED with it** | The v1.1 workflow runs on `push` to `main`, so a bad push is detected after the fact — but detection is not blocking. ONLY branch protection requiring the `harness` job blocks a direct push. Protection is NOT installed (pending branch protection, enabled after this PR merges; the GitHub App write access was fixed Nov 9, 2026). Until it is, a direct push can land; the install is therefore incomplete without it. This dependency is stated, not hidden. |
| (d) | A change that passes the script but breaks the live site | **PARTLY BLOCKED; remaining gaps named** | The concrete case tested: a broken relative link (`assets/missing-poster.jpg`). v1.0 exits 0 (no relative-asset check — the gap was real); v1.1 exits 1 with `relative_assets` FAIL naming the file (BYP-D1/D2). Remaining gaps after v1.1, named honestly (§8): JS/CSS syntax errors, visual/layout regression, content correctness, performance/accessibility. None of these is checked. |
| (e) | Editing the script to force a pass, disabling a check, or skipping the script | **BYPASS BLOCKED** (script) / **PROCEDURE-ONLY** (skipping) | `--skip`, `--disable`, `--ignore` are all rejected by argparse (exit 3, usage error); no such flag is defined in the script — the words appear only in the docstring prohibition (BYP-E-*). A tampered script is handled by (a). "Skipping the script" entirely (never running it) cannot be detected by the script itself; it is a procedure violation, detectable only by the missing record — until CI + branch protection are installed, the record is the enforcement (§9). |

**v1.0 workflow flaw found during this review (not in the founder's list):** the v1.0 draft ran neither `--diff` nor `--html`, so it checked the LIVE site and the checkout's secrets/stubs only — it never tested the change itself. A PR that broke the canonical or added a dead link would have passed the v1.0 job. v1.1 fixes this: the job runs `--html index.html --diff-file change.diff` (verified by static inspection: BYP-E-wf10/wf11).

## 11. Files
- `HARNESS_SPEC_2026-11-09.md` — v1.0 spec (workspace only; kept intact as the pilot record, not in this repo).
- `HARNESS_SPEC_2026-11-09_v1.1.md` — this file.
- `checks/check_popaurmaa.py` — v1.0 check script (workspace only; kept intact, not in this repo).
- `checks/check_popaurmaa_v1.1.py` — v1.1 check script (Python standard library only).
- `BASELINE_2026-11-09.md` — v1.0 baseline (workspace only; kept intact, not in this repo).
- `BASELINE_2026-11-09_v1.1.md` — v1.1 baseline (workspace only; new checks, same live site vs HEAD — the pilot record, not in this repo).
- `BYPASS_TESTS_2026-11-09.md` — Finding 1 + Finding 4 test log.
- `END_TO_END_LOW_RUN_PLAN_2026-11-09.md` — Finding 3 run plan (no candidate found; plan ready).
- `workflow-draft.yml` — v1.0 workflow draft (workspace only; kept intact, not in this repo).
- `workflow-draft-v1.1.yml` — v1.1 workflow draft (workspace only; installed as `.github/workflows/harness.yml` by this PR).
- `CODEOWNERS-draft` — human review gate for `harness/` and `.github/` (workspace only; installed as `.github/CODEOWNERS` by this PR).
- `evidence/repo-HEAD-5a887858/` — v1.0 read-only snapshot of the repo at HEAD `5a887858` (workspace only; text files + the site bundle zip; `assets/` media files were not copied — binary media, not scanned by the checks).
- `evidence/repo-HEAD-5a887858-full/` — v1.1 complete snapshot of the repo at HEAD `5a887858` (workspace only; all files including the 7 asset media files downloaded from the live site; SHA-256-verified identical to the zip contents for the three files checked). Used for the v1.1 baseline.
- `_test-scratch/` — synthetic test repos, diffs, and the two test drivers (`test_finding1.py`, `test_finding4.py`) (workspace only; scratch repos were removed after the runs; the drivers and diffs are kept as the reproducible evidence).
