#!/usr/bin/env python3
"""popaurmaa.com harness checks v1.1 — Funding All Ventures Business.

Builds on the v1.0 pilot (Nov 9, 2026; baseline 7 PASS / 0 FAIL / 2 NOT RUN).
v1.1 resolves the founder's four review findings (Nov 9, 2026, ~18:31 CST;
status CONDITIONAL PASS). The v1.0 files are kept intact; this is the v1.1
revision. Pilot stays limited to popaurmaa.com.

WHAT v1.1 CHANGES (vs v1.0):
  * Relative-asset coverage (Finding 2): img/video/poster/script/link
    relative URLs are resolved and checked — local existence in the repo
    checkout, plus a live fetch when the page under review IS the live
    page. CSS url(...) references are collected too (absolute ones join
    the external-link check).
  * Safe ZIP content scanning (Finding 2): the repo's .zip bundle is read
    with hard limits (max entries, max total bytes, max single-file
    bytes; no symlinks, no absolute paths, no path traversal) and its
    TEXT contents are scanned for the same credential patterns. Nothing
    from the zip is executed. A limit breach is a FAIL, never a silent
    skip. Binary files are counted as skipped, not hidden.
  * HIGH approval mechanism (Finding 4): a failed security check and a
    HIGH change awaiting approval are now DISTINCT outcomes with distinct
    exit codes and resolution paths (see "Exit codes" below). A HIGH
    change with a valid, verifiable approval record may proceed.
  * Scope guard (Finding 1): accepts a unified diff file (--diff-file)
    so the workflow can classify a multi-file PR. The guard no longer
    reports HIGH as a FAIL — classification is not a security failure;
    the blocking for HIGH now lives in the `approval` check.
  * The workflow (workflow-draft-v1.1.yml) runs the script from the base
    branch, guards against harness-file tampering, and surfaces the two
    blocking reasons distinctly. See the spec §10 for the bypass
    scenarios tested.

ENFORCEMENT RULES (read before changing anything in this file):
  * This script is the check. It is never edited to make a failing check
    pass. There are no --skip, --ignore, or --disable flags, and none may
    be added. A check that cannot run is reported NOT RUN with the reason;
    a mandatory check that cannot run (e.g. the live site cannot be
    fetched) is a FAIL, not a pass.
  * The secret-pattern allowlist below is hardcoded with reasons. It
    covers public identifiers that are meant to appear in client-side
    code (the GA4 measurement ID, the tawk.to widget ID). It cannot be
    extended from the command line. Anything that looks like a credential
    and is not on the allowlist is a FAIL.
  * This script does not commit, push, publish, or change anything. It
    only reads and reports. Deployment stays a separate, human-approved
    step through the GitHub connector (each write shows a fresh approval
    card).
  * Without CI + branch protection, enforcement is this script plus the
    written record — not a server-side gate. The workflow draft
    (workflow-draft-v1.1.yml) is what would make it a gate; until it is
    approved and installed, a passing run must be recorded by hand.

Exit codes:
  0 = PASS / APPROVED — every mandatory check passed; a HIGH change had
      a valid approval record. The change may proceed.
  1 = FAILED — at least one mandatory security check failed. The change
      is unsafe. Resolution: fix the change itself. Never edit this
      script to make it pass. A failed check cannot be overridden by
      any approval record.
  2 = AWAITING_APPROVAL — no security check failed, but a HIGH-tier
      change has no valid approval record. The change is safe but not
      yet authorized. Resolution: obtain and record founder approval
      (harness/APPROVAL-*.md) and re-run. Still blocks merging.
  3 = usage error (bad flags / missing required arguments).

Usage:
  python3 check_popaurmaa_v1.1.py [--live | --html PATH] [--repo-dir DIR]
      [--diff OLD NEW | --diff-file PATH] [--base-sha SHA] [--head-sha SHA]
      [--approval-dir DIR] [--expect MARKER]
    --live            fetch https://popaurmaa.com/ and check it (default)
    --html PATH       check a local HTML file instead of the live site
                      (the PR's index.html in CI)
    --repo-dir DIR    local copy of the repo (secret scan, stub checks,
                      site-config.js links, relative-asset existence)
    --diff OLD NEW    scope-guard: classify the change between two files
    --diff-file PATH  scope-guard: classify a unified diff (multi-file;
                      what CI passes). Mutually exclusive with --diff.
    --base-sha SHA    base commit SHA (approval verification)
    --head-sha SHA    HEAD commit SHA (approval verification, revert cmd)
    --approval-dir DIR directory holding harness/APPROVAL-*.md records
                      (default: <repo-dir>/harness, else ./harness)
    --expect MARKER   post-deploy verify: marker that must be in live HTML

Python standard library only. No new dependencies.
"""

import argparse
import difflib
import hashlib
import html as htmlmod  # noqa: F401  (kept for parity with v1.0)
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from html.parser import HTMLParser
from pathlib import Path

SITE_URL = "https://popaurmaa.com/"
EXPECTED_CANONICAL = "https://popaurmaa.com/"
EXPECTED_TITLE = "Popâ Ur-Mää Global Consulting Enterprise"
EXPECTED_OG = {
    "og:type": "website",
    "og:url": "https://popaurmaa.com/",
    "og:title": "Popâ Ur-Mää Global Consulting Enterprise",
    "og:description": (
        "Popâ Ur-Mää Global Consulting Enterprise — music, business, "
        "technology, culture, and education. Founded by Byron E. Burke."
    ),
    "og:image": "https://popaurmaa.com/assets/enterprise-emblem.webp",
}
USER_AGENT = {"User-Agent": "Mozilla/5.0 (compatible; Popa2Harness/1.1)"}
# Full browser header set. VERIFIED Nov 9, 2026: Shopify returns HTTP 403
# to a bare-script request (urllib with only a User-Agent) while the same
# URL returns 200 to curl and to a full browser header set. The check must
# verify the link works for a visitor, so it sends browser headers. This
# is not a way to hide a dead link: a genuinely dead link still fails
# (404 / DNS error / timeout), and every failure is printed, never
# silently passed.
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0 Safari/537.36"),
    "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
               "*/*;q=0.8"),
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}
TIMEOUT = 20

# ZIP content-scan limits (Finding 2). Recorded in the spec §6. The real
# bundle (VERIFIED Nov 9, 2026) is 12 entries / 17,108,736 uncompressed
# bytes / largest single file 10,649,740 bytes, so these caps pass it with
# wide margin while still bounding a decompression bomb.
MAX_ZIP_ENTRIES = 500
MAX_ZIP_TOTAL_BYTES = 100_000_000
MAX_ZIP_FILE_BYTES = 25_000_000

# ---------------------------------------------------------------- results
# Statuses: PASS, FAIL, NOT RUN, AWAITING_APPROVAL. AWAITING_APPROVAL is
# NOT a failure of a security check — it is the approval gate (Finding 4).
RESULTS = []  # (name, status, detail)


def report(name, status, detail=""):
    """Never silently pass a failure. AWAITING_APPROVAL blocks merging
    just like FAIL, but for a different reason (see exit codes)."""
    assert status in ("PASS", "FAIL", "NOT RUN", "AWAITING_APPROVAL")
    RESULTS.append((name, status, detail))


# ---------------------------------------------------------------- fetching
def http_get(url, timeout=TIMEOUT):
    """GET with browser headers, following redirects. Returns
    (status_code, body_bytes) or raises urllib.error.URLError.

    Some hosts (VERIFIED Nov 9, 2026: Shopify, Facebook) reject
    bare-script requests with 403/400 while serving the same URL to a
    browser. The first attempt uses a standard browser header set; a
    400/403 is retried once with fuller navigation headers (Sec-Fetch).
    Only if both attempts fail is the URL reported failed. A genuinely
    dead link still fails (404, DNS error, timeout) and is printed, never
    silently passed."""
    try:
        req = urllib.request.Request(url, headers=BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code not in (400, 403):
            raise
        retry_headers = dict(BROWSER_HEADERS)
        retry_headers.update({
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Upgrade-Insecure-Requests": "1",
        })
        req = urllib.request.Request(url, headers=retry_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()


# ---------------------------------------------------------------- parsing
class PageParser(HTMLParser):
    """Collects ids, hrefs, and every URL-bearing attribute from the page:
    links, images, video sources/posters, scripts, stylesheets, iframes,
    and srcset entries. v1.1 addition (Finding 2): relative assets were
    invisible to the v1.0 check — they are collected here now."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.hrefs = []
        self.title = ""
        self._in_title = False
        self.canonical = None
        self.og = {}
        self.json_ld = []
        self._in_ld = False
        self._ld_buf = []
        self.relative_urls = []  # (tag, attr, raw value)
        self.absolute_urls = []  # (tag, attr, raw value)

    def _collect(self, tag, attr, value):
        if not value:
            return
        v = value.strip()
        if not v:
            return
        if v.startswith("#") or v.startswith(("data:", "mailto:", "tel:",
                                              "javascript:")):
            return
        if re.match(r"https?://", v) or v.startswith("//"):
            self.absolute_urls.append((tag, attr, v))
        else:
            self.relative_urls.append((tag, attr, v))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if "id" in a:
            self.ids.add(a["id"])
        if tag == "a" and "href" in a:
            self.hrefs.append(a["href"])
            self._collect(tag, "href", a["href"])
        if tag == "link":
            if a.get("rel") == "canonical":
                self.canonical = a.get("href")
            if "href" in a:
                self._collect(tag, "href", a["href"])
        if tag == "meta" and a.get("property", "").startswith("og:"):
            self.og[a["property"]] = a.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag == "script" and a.get("type") == "application/ld+json":
            self._in_ld = True
            self._ld_buf = []
        if tag == "script" and "src" in a:
            self._collect(tag, "src", a["src"])
        if tag == "img":
            if "src" in a:
                self._collect(tag, "src", a["src"])
            if "srcset" in a:
                for part in a["srcset"].split(","):
                    self._collect(tag, "srcset", part.strip().split(" ")[0])
        if tag == "source" and "src" in a:
            self._collect(tag, "src", a["src"])
        if tag == "video":
            if "src" in a:
                self._collect(tag, "src", a["src"])
            if "poster" in a:
                self._collect(tag, "poster", a["poster"])
        if tag == "iframe" and "src" in a:
            self._collect(tag, "src", a["src"])

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script" and self._in_ld:
            self._in_ld = False
            self.json_ld.append("".join(self._ld_buf))

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_ld:
            self._ld_buf.append(data)

# ---------------------------------------------------------------- checks
def check_live_fetch():
    try:
        status, body = http_get(SITE_URL)
    except Exception as exc:  # noqa: BLE001 - any fetch failure is a FAIL
        report("live_http", "FAIL", f"could not fetch {SITE_URL}: {exc}")
        return None
    if status != 200:
        report("live_http", "FAIL", f"{SITE_URL} returned HTTP {status}")
        return None
    report("live_http", "PASS",
           f"{SITE_URL} HTTP 200, {len(body)} bytes")
    return body.decode("utf-8", errors="replace")


def check_required_tags(html):
    if html is None:
        report("required_tags", "FAIL", "no HTML to check (live fetch failed)")
        return None
    p = PageParser()
    p.feed(html)
    problems = []
    if p.canonical != EXPECTED_CANONICAL:
        problems.append(f"canonical is {p.canonical!r}, expected "
                        f"{EXPECTED_CANONICAL!r}")
    for key, want in EXPECTED_OG.items():
        got = p.og.get(key)
        if got is None:
            problems.append(f"missing {key}")
        elif got != want:
            problems.append(f"{key} is {got!r}, expected {want!r}")
    if not p.json_ld:
        problems.append("no JSON-LD block found")
    else:
        try:
            ld = json.loads(p.json_ld[0])
        except json.JSONDecodeError as exc:
            problems.append(f"JSON-LD does not parse: {exc}")
            ld = None
        if ld is not None:
            if ld.get("@type") != "Organization":
                problems.append(f"JSON-LD @type is {ld.get('@type')!r}, "
                                "expected 'Organization'")
            if "sameAs" in ld:
                problems.append("JSON-LD contains sameAs (must be absent)")
    if problems:
        report("required_tags", "FAIL", "; ".join(problems))
    else:
        report("required_tags", "PASS",
               "canonical + all 5 OG tags present with expected values; "
               "JSON-LD parses as Organization without sameAs")
    return p


def check_metadata_consistency(parser):
    if parser is None:
        report("metadata_consistency", "FAIL",
               "no parsed page (required-tags check failed)")
        return
    problems = []
    if parser.title.strip() != EXPECTED_TITLE:
        problems.append(f"title is {parser.title.strip()!r}")
    if parser.og.get("og:title", "").strip() != EXPECTED_TITLE:
        problems.append("og:title does not match <title>")
    if parser.canonical != parser.og.get("og:url"):
        problems.append("canonical and og:url disagree")
    if problems:
        report("metadata_consistency", "FAIL", "; ".join(problems))
    else:
        report("metadata_consistency", "PASS",
               "title, canonical, and og:url agree")


def check_internal_anchors(parser):
    if parser is None:
        report("internal_anchors", "FAIL", "no parsed page")
        return
    missing = sorted({h[1:] for h in parser.hrefs
                      if h.startswith("#") and h[1:] not in parser.ids})
    if missing:
        report("internal_anchors", "FAIL",
               f"anchor(s) with no matching id: {missing}")
    else:
        n = len([h for h in parser.hrefs if h.startswith("#")])
        report("internal_anchors", "PASS",
               f"{n} internal anchor href(s), all resolve to an id")


def collect_external_urls(html, repo_dir):
    """Absolute http(s) URLs in the page, plus the venture URLs rendered
    client-side from site-config.js (they are real links on the live page
    even though they are not hrefs in index.html), plus absolute url(...)
    references from the repo's .css files (v1.1: the Google Fonts import
    in styles.css was invisible to v1.0)."""
    urls = set(re.findall(r'https?://[^\s"\'<>]+', html))
    if repo_dir:
        root = Path(repo_dir)
        cfg = root / "site-config.js"
        if cfg.exists():
            urls |= set(re.findall(r'https?://[^\s"\'<>]+',
                                   cfg.read_text(encoding="utf-8",
                                                 errors="replace")))
        for css in sorted(root.rglob("*.css")):
            try:
                text = css.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                continue
            for m in re.finditer(r"url\(\s*['\"]?(https?://[^)'\"\s]+)",
                                 text):
                urls.add(m.group(1))
    # Strip trailing punctuation the regex may have caught.
    return sorted(u.rstrip(".,);") for u in urls)


def check_external_links(html, repo_dir):
    if html is None:
        report("external_links", "FAIL", "no HTML to check")
        return
    urls = collect_external_urls(html, repo_dir)
    failures = []
    ok = 0
    for url in urls:
        try:
            status, _ = http_get(url)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{url} -> error: {exc}")
            continue
        if status != 200:
            failures.append(f"{url} -> HTTP {status}")
        else:
            ok += 1
    if failures:
        report("external_links", "FAIL",
               f"{ok} OK, {len(failures)} failed: " + "; ".join(failures))
    else:
        report("external_links", "PASS",
               f"{len(urls)} external URL(s) checked, all HTTP 200")


def _strip_url_suffix(raw):
    """Split a relative URL into (path, query, fragment)."""
    path = raw.split("#", 1)[0].split("?", 1)[0]
    return path


def check_relative_assets(parser, repo_dir, from_live):
    """v1.1 (Finding 2). Every relative image / video / poster / script /
    stylesheet / local-file URL on the page must resolve:
      * in the repo checkout (local existence) — this is the gate for a
        PR, where the live site does not have the PR's new assets yet;
      * AND, when the page under review IS the live page, by fetching it
        from the live site (HTTP 200).
    A relative path that escapes the repo root (``..``) is a FAIL.
    In --html mode the live-fetch half is skipped on purpose: the live
    site cannot have assets that only exist in the PR. The skip is
    stated in the detail, never silent."""
    if parser is None:
        report("relative_assets", "FAIL", "no parsed page")
        return
    refs = sorted({raw for _, _, raw in parser.relative_urls})
    # Relative url(...) references inside the repo's .css files (a CSS
    # file lives at the repo root here, so its relative paths resolve
    # against the repo root; a stylesheet in a subfolder would resolve
    # against that subfolder — handled by joining to the css file's dir).
    css_refs = []  # (css_rel_dir, raw)
    if repo_dir:
        for css in sorted(Path(repo_dir).rglob("*.css")):
            try:
                text = css.read_text(encoding="utf-8", errors="strict")
            except (UnicodeDecodeError, OSError):
                continue
            for m in re.finditer(r"url\(\s*['\"]?([^)'\"\s]+)", text):
                raw = m.group(1).strip()
                if raw.startswith(("http://", "https://", "//", "data:")):
                    continue
                css_refs.append((css.parent.relative_to(Path(repo_dir)),
                                 raw))
    problems = []
    checked_local = 0
    checked_live = 0
    for raw in refs:
        path = _strip_url_suffix(raw)
        if not path:
            continue
        target = (Path(repo_dir) / path) if repo_dir else None
        if target is not None:
            try:
                resolved = target.resolve()
                root = Path(repo_dir).resolve()
                if not (resolved == root or root in resolved.parents):
                    problems.append(f"{raw} escapes the repo root")
                    continue
            except OSError as exc:
                problems.append(f"{raw} cannot be resolved: {exc}")
                continue
            checked_local += 1
            if not resolved.is_file():
                problems.append(f"{raw} missing from the repo checkout")
                continue
        if from_live:
            live_url = SITE_URL.rstrip("/") + "/" + path
            try:
                status, _ = http_get(live_url)
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{raw} live fetch failed: {exc}")
                continue
            if status != 200:
                problems.append(f"{raw} live returned HTTP {status}")
            else:
                checked_live += 1
    for css_dir, raw in css_refs:
        path = _strip_url_suffix(raw)
        if not path or path.startswith("#"):
            continue
        target = Path(repo_dir) / css_dir / path if repo_dir else None
        if target is not None:
            try:
                resolved = target.resolve()
                root = Path(repo_dir).resolve()
                if not (resolved == root or root in resolved.parents):
                    problems.append(f"css {raw} escapes the repo root")
                    continue
            except OSError as exc:
                problems.append(f"css {raw} cannot be resolved: {exc}")
                continue
            checked_local += 1
            if not resolved.is_file():
                problems.append(f"css {raw} missing from the repo checkout")
    if repo_dir is None:
        detail = (f"{len(refs)} relative URL(s) found, but no --repo-dir "
                  "given so local existence could not be checked")
        report("relative_assets", "FAIL", detail)
        return
    live_note = (f"; {checked_live} live-fetched OK" if from_live else
                 "; live fetch skipped (local file under review — the "
                 "live site does not have the PR's new assets yet)")
    if problems:
        report("relative_assets", "FAIL",
               f"{checked_local} checked locally{live_note}: "
               + "; ".join(problems))
    else:
        report("relative_assets", "PASS",
               f"{checked_local} relative asset(s) exist in the repo "
               f"checkout{live_note}")

# ---------------------------------------------------------------- secrets
SECRET_PATTERNS = [
    ("AWS access key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GitHub token", re.compile(r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("Slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("assigned credential",
     re.compile(r"(?i)(api[_-]?key|api[_-]?token|access[_-]?token|"
                r"client[_-]?secret|password|passwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]")),
    ("AWS secret assignment",
     re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"][^'\"]{20,}['\"]")),
]
# Public identifiers that are MEANT to appear in client-side code. Hardcoded
# with reasons; this list cannot be extended from the command line.
ALLOWLIST = [
    ("G-RHE021T26E",
     "GA4 measurement ID — a public analytics identifier, not a credential"),
    ("6adb6021df87b834702866f1/1k5kev15a",
     "tawk.to widget ID — a public embed identifier, not a credential"),
]
SCANNABLE_SUFFIXES = {".html", ".js", ".css", ".xml", ".txt", ".md", ""}


def _scan_text_for_secrets(text, where, hits):
    for label, pattern in SECRET_PATTERNS:
        for m in pattern.finditer(text):
            found = m.group(0)
            if any(a in found for a, _ in ALLOWLIST):
                continue
            hits.append(f"{where}: {label} ({found[:40]!r}…)")


def _scan_zip_contents(zpath, hits):
    """v1.1 (Finding 2). Read a .zip bundle's TEXT contents under hard
    limits and scan them for the same credential patterns. Nothing is
    extracted to disk and nothing is executed: entries are read into
    memory one at a time, bounded by the limits. A limit breach or an
    unsafe entry is a FAIL, never a silent skip. Binary entries are
    counted as skipped, not hidden. Returns a one-line summary."""
    try:
        zf = zipfile.ZipFile(zpath)
    except zipfile.BadZipFile:
        hits.append(f"{zpath.name}: unreadable zip archive")
        return f"{zpath.name}: unreadable"
    with zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            hits.append(f"{zpath.name}: {len(infos)} entries exceeds the "
                        f"limit of {MAX_ZIP_ENTRIES}")
            return f"{zpath.name}: entry-count limit exceeded"
        total = sum(i.file_size for i in infos)
        if total > MAX_ZIP_TOTAL_BYTES:
            hits.append(f"{zpath.name}: {total} uncompressed bytes exceeds "
                        f"the limit of {MAX_ZIP_TOTAL_BYTES}")
            return f"{zpath.name}: total-size limit exceeded"
        scanned = 0
        skipped_binary = 0
        for info in infos:
            if info.is_dir():
                continue
            name = info.filename
            # Unsafe entries: absolute paths, traversal, symlinks.
            # (The symlink test must mask with 0o170000 — the file-type
            # bits. A bare 0o120000 mask is truthy for regular files too;
            # v1.0's reconnaissance tripped on exactly this.)
            mode = (info.external_attr >> 16) & 0o170000
            if (name.startswith("/") or name.startswith("\\")
                    or ".." in Path(name).parts or mode == 0o120000):
                hits.append(f"{zpath.name}: unsafe entry {name!r} "
                            "(absolute path, traversal, or symlink)")
                continue
            if info.file_size > MAX_ZIP_FILE_BYTES:
                hits.append(f"{zpath.name}: entry {name!r} is "
                            f"{info.file_size} bytes, over the per-file "
                            f"limit of {MAX_ZIP_FILE_BYTES}")
                continue
            try:
                data = zf.read(info)
            except (zipfile.BadZipFile, OSError, RuntimeError) as exc:
                hits.append(f"{zpath.name}: cannot read entry {name!r}: {exc}")
                continue
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                skipped_binary += 1
                continue
            scanned += 1
            _scan_text_for_secrets(text, f"{zpath.name}:{name}", hits)
        # Suspicious filenames (kept from v1.0).
        bad = [i.filename for i in infos
               if re.search(r"\.env$|\.pem$|\.key$|credentials|secret|"
                            r"password|\.p12$|\.pfx$", i.filename, re.I)]
        hits += [f"{zpath.name}: suspicious entry {n!r}" for n in bad]
        return (f"{zpath.name}: {len(infos)} entries, {scanned} text "
                f"scanned, {skipped_binary} binary skipped, suspicious "
                f"names: {bad if bad else 'none'}")


def check_secret_scan(repo_dir):
    if not repo_dir:
        report("secret_scan", "NOT RUN",
               "no --repo-dir given; pass the repo copy to enable the scan")
        return
    root = Path(repo_dir)
    if not root.is_dir():
        report("secret_scan", "FAIL", f"--repo-dir {repo_dir} is not a directory")
        return
    hits = []
    scanned = 0
    skipped_binary = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() == ".zip":
            continue
        if path.suffix.lower() not in SCANNABLE_SUFFIXES and path.suffix:
            skipped_binary += 1
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            skipped_binary += 1
            continue
        scanned += 1
        _scan_text_for_secrets(text, str(path.relative_to(root)), hits)
    zip_notes = []
    for zpath in sorted(root.rglob("*.zip")):
        zip_notes.append(_scan_zip_contents(zpath, hits))
    zip_note = "; ".join(zip_notes) if zip_notes else "no .zip in repo copy"
    if hits:
        report("secret_scan", "FAIL", "; ".join(hits))
    else:
        report("secret_scan", "PASS",
               f"{scanned} text file(s) scanned, {skipped_binary} binary "
               f"skipped (counted, not hidden), no credential patterns "
               f"outside the documented allowlist; {zip_note}")


# ---------------------------------------------------------------- scope guard
HIGH_PATTERNS = [
    ("price", re.compile(r"\$\s?\d|\bprice\b", re.I)),
    ("legal text", re.compile(r"refund|privacy|terms of|liability|"
                              r"all rights reserved|disclaimer", re.I)),
    ("contact info", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|mailto:|"
                                r"contactEmail", re.I)),
    ("redirect", re.compile(r"http-equiv=.refresh|location\.replace|"
                            r"CNAME", re.I)),
    ("chat widget", re.compile(r"tawk", re.I)),
    ("brand identity", re.compile(r"<title>|brand-name|"
                                  r"src=\"assets/enterprise-emblem", re.I)),
]
MEDIUM_PATTERNS = [
    ("metadata", re.compile(r"canonical|og:|application/ld\+json|"
                            r"sameAs", re.I)),
    ("new anchor section", re.compile(r"<section[^>]*\bid=|<[^>]+ id=\"", re.I)),
    ("external link change", re.compile(r"https?://", re.I)),
]


def _classify_lines(added, removed, touched_paths):
    """Shared classifier. Returns (tier, detail). The tier is a
    classification, not a verdict: v1.1 no longer reports HIGH as a FAIL
    here. Blocking for HIGH lives in the `approval` check (Finding 4)."""
    if not added and not removed and not touched_paths:
        return "LOW", "no differences (LOW, nothing changed)"
    changed = "\n".join(added + removed)
    high_hits = sorted({label for label, pat in HIGH_PATTERNS
                        if pat.search(changed)})
    med_hits = sorted({label for label, pat in MEDIUM_PATTERNS
                       if pat.search(changed)})
    touched_config = any("site-config.js" in p for p in touched_paths)
    harness_changed = [p for p in touched_paths
                       if p.startswith("harness/checks/")
                       or p.startswith(".github/workflows/")]
    if high_hits:
        tier = "HIGH"
    elif med_hits or touched_config:
        tier = "MEDIUM"
    else:
        tier = "LOW"
    detail = (f"+{len(added)} / -{len(removed)} lines; "
              f"files: {sorted(touched_paths) or 'none'}; "
              f"HIGH patterns: {high_hits or 'none'}; "
              f"MEDIUM patterns: {med_hits or 'none'}")
    if harness_changed:
        detail += ("; HARNESS FILES CHANGED: "
                   f"{sorted(harness_changed)} — the workflow guard "
                   "rejects this; harness changes need a separate "
                   "founder-reviewed PR")
    if tier == "HIGH":
        detail += ("; HIGH: mandatory founder approval — see the "
                   "`approval` check (exit 2 while awaiting it)")
    elif tier == "MEDIUM":
        detail += ("; MEDIUM: independent second readback required "
                   "before any commit")
    else:
        detail += "; LOW: may proceed after all checks pass"
    return tier, detail


def classify_diff(old_path, new_path):
    """Single file pair (local use). Returns (tier, diff_sha256)."""
    old = Path(old_path).read_text(encoding="utf-8", errors="replace")
    new = Path(new_path).read_text(encoding="utf-8", errors="replace")
    diff_lines = list(difflib.unified_diff(
        old.splitlines(), new.splitlines(),
        fromfile=old_path, tofile=new_path, lineterm=""))
    added = [ln[1:] for ln in diff_lines if ln.startswith("+")
             and not ln.startswith("+++")]
    removed = [ln[1:] for ln in diff_lines if ln.startswith("-")
               and not ln.startswith("---")]
    diff_sha = hashlib.sha256(
        "\n".join(diff_lines).encode("utf-8")).hexdigest()
    tier, detail = _classify_lines(added, removed, [old_path, new_path])
    report("scope_guard", "PASS", f"classification {tier} — {detail}")
    return tier, diff_sha


def classify_diff_file(diff_path):
    """Unified diff file (multi-file; what CI passes). Returns
    (tier, diff_sha256 of the file bytes as supplied)."""
    raw = Path(diff_path).read_bytes()
    diff_sha = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8", errors="replace")
    added, removed, touched = [], [], set()
    for ln in text.splitlines():
        if ln.startswith("+++ "):
            p = ln[4:].strip()
            if p.startswith("b/"):
                p = p[2:]
            if p != "/dev/null":
                touched.add(p)
            continue
        if ln.startswith("--- "):
            continue
        if ln.startswith(("diff --git ", "index ", "@@")):
            continue
        if ln.startswith("+"):
            added.append(ln[1:])
        elif ln.startswith("-"):
            removed.append(ln[1:])
    tier, detail = _classify_lines(added, removed, touched)
    report("scope_guard", "PASS", f"classification {tier} — {detail}")
    return tier, diff_sha


# ---------------------------------------------------------------- stubs
def check_redirect_stubs(repo_dir):
    if not repo_dir:
        report("redirect_stubs", "NOT RUN",
               "no --repo-dir given; stubs live in the repo copy")
        return
    root = Path(repo_dir)
    stubs = {
        "about-founder/index.html": "https://popaurmaa.com/#about",
        "f/rolls-royce-presents-black-badge-ghost-series-ii/index.html":
            "https://popaurmaa.com/#media",
        "f/rude-tymz-entertainment-a-bold-step-into-luxury-footwear/index.html":
            "https://popaurmaa.com/#ventures",
    }
    problems = []
    checked = 0
    for rel, target in stubs.items():
        path = root / rel
        if not path.exists():
            problems.append(f"missing stub {rel}")
            continue
        checked += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        if target not in text:
            problems.append(f"{rel} does not redirect to {target}")
        if f'rel="canonical" href="{target}"' not in text:
            problems.append(f"{rel} canonical is not {target}")
    if problems:
        report("redirect_stubs", "FAIL", "; ".join(problems))
    else:
        report("redirect_stubs", "PASS",
               f"{checked} redirect stub(s) point at their matching "
               "homepage sections with matching canonicals")


# ---------------------------------------------------------------- post-deploy
def post_deploy_verify(marker, head_sha):
    try:
        status, body = http_get(SITE_URL)
    except Exception as exc:  # noqa: BLE001
        report("post_deploy_verify", "FAIL",
               f"could not re-fetch live site: {exc}")
        return
    if status != 200:
        report("post_deploy_verify", "FAIL", f"live site HTTP {status}")
        return
    text = body.decode("utf-8", errors="replace")
    if marker and marker not in text:
        report("post_deploy_verify", "FAIL",
               f"expected marker not in live HTML: {marker!r}")
        return
    revert = (f"git revert {head_sha}" if head_sha else
              "git revert <HEAD-SHA>  (re-run with --head-sha)")
    report("post_deploy_verify", "PASS",
           f"live HTML re-fetched (HTTP 200, {len(body)} bytes); "
           f"marker present. Rollback if needed: {revert} "
           "(via the GitHub connector — a fresh approval card is shown), "
           "then re-run this script to confirm the live page is back.")


# ---------------------------------------------------------------- approval
# Approval record format (spec §7). A file harness/APPROVAL-<YYYYMMDD>-
# <shortsha>.md in the PR, containing machine-readable key: value lines:
#   tier: HIGH
#   change-description: <one line>
#   base-sha: <40-hex SHA of the base commit>
#   head-sha: <40-hex SHA of the change commit the approval covers>
#   diff-sha256: <sha256 of `git diff <base> <head> -- . ':!harness/APPROVAL-*'`>
#   founder-approval-words: "<the founder's exact words>"
#   approved-date: <YYYY-MM-DD>
#   recorded-by: <name or agent>
# The record is only as trustworthy as the PR process + branch protection:
# the script verifies the record EXISTS, is well-formed, and MATCHES the
# change (hash + ancestry). It cannot verify the founder actually typed
# the words — that trust comes from the approval happening in the
# founder's own words in chat, recorded by the agent that received them.
APPROVAL_REQUIRED_KEYS = ("tier", "change-description", "base-sha",
                          "head-sha", "diff-sha256",
                          "founder-approval-words", "approved-date")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _git(repo_dir, args, timeout=30):
    try:
        out = subprocess.run(["git", "-C", str(repo_dir)] + args,
                             capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return False, ""
    return out.returncode == 0, out.stdout


def _parse_approval_record(path):
    rec = {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9-]+):\s*(.*)$", ln)
        if m:
            val = m.group(2).strip()
            if len(val) >= 2 and val[0] == val[-1] == '"':
                val = val[1:-1]
            rec[m.group(1)] = val
    return rec


def _validate_approval_record(rec, diff_sha, head_sha, repo_dir):
    """Returns (valid, reason). `head_sha` is the current HEAD under
    review (the PR head / push SHA)."""
    if rec is None:
        return False, "unreadable record"
    missing = [k for k in APPROVAL_REQUIRED_KEYS if not rec.get(k)]
    if missing:
        return False, f"missing keys: {missing}"
    if rec["tier"] != "HIGH":
        return False, f"tier is {rec['tier']!r}, expected 'HIGH'"
    if not _SHA_RE.match(rec["base-sha"]):
        return False, "base-sha is not a 40-hex SHA"
    if not _SHA_RE.match(rec["head-sha"]):
        return False, "head-sha is not a 40-hex SHA"
    if diff_sha is None:
        return False, "no diff was supplied, so the record's hash cannot be verified"
    if rec["diff-sha256"] != diff_sha:
        return False, ("diff-sha256 mismatch — the change was amended "
                       "after approval, or the record covers a different "
                       "change")
    if not _DATE_RE.match(rec["approved-date"]):
        return False, "approved-date is not YYYY-MM-DD"
    try:
        import datetime
        datetime.date.fromisoformat(rec["approved-date"])
    except ValueError:
        return False, "approved-date is not a real calendar date"
    if not rec["founder-approval-words"].strip():
        return False, "founder-approval-words is empty"
    # Ancestry: the approved change commit must be an ancestor of (or
    # equal to) the HEAD under review. This rejects a record whose change
    # was rewritten after approval (amend/rebase creates a new commit
    # that is not a descendant of the approved one).
    ancestry_note = ""
    if repo_dir and head_sha:
        ok, _ = _git(repo_dir, ["merge-base", "--is-ancestor",
                                rec["head-sha"], head_sha])
        if not ok:
            # Distinguish "git failed" from "not an ancestor": check the
            # record commit exists at all.
            exists, _ = _git(repo_dir, ["cat-file", "-e",
                                        rec["head-sha"] + "^{commit}"])
            if exists:
                return False, ("approved head-sha is not an ancestor of "
                               "the HEAD under review — the change was "
                               "rewritten after approval")
            ancestry_note = (" (ancestry not verified: git could not "
                             "resolve the approved commit in this copy)")
    if ancestry_note:
        return True, "valid (hash match)" + ancestry_note
    return True, "valid"


def check_approval(tier, diff_sha, base_sha, head_sha, repo_dir,
                   approval_dir):
    """Finding 4. Decides whether a HIGH change may proceed.
    LOW: no approval required. MEDIUM: second readback is a manual step
    the script cannot verify (NOT RUN, stated plainly). HIGH: a valid
    approval record is required; without one the check reports
    AWAITING_APPROVAL (exit 2), never a security FAIL."""
    if tier is None:
        report("approval", "NOT RUN",
               "no change was classified (no --diff/--diff-file), so "
               "there is nothing to approve")
        return
    if tier == "LOW":
        report("approval", "PASS",
               "LOW change — no founder approval required")
        return
    if tier == "MEDIUM":
        report("approval", "NOT RUN",
               "MEDIUM change — the independent second readback is a "
               "manual step; record it in the PR before merging. The "
               "workflow cannot verify a human readback.")
        return
    # HIGH from here.
    adir = None
    if approval_dir:
        adir = Path(approval_dir)
    elif repo_dir:
        adir = Path(repo_dir) / "harness"
    else:
        adir = Path("harness")
    if not adir.is_dir():
        report("approval", "AWAITING_APPROVAL",
               f"HIGH change with no approval record: directory {adir} "
               "does not exist. Resolution: obtain founder approval and "
               "add harness/APPROVAL-<date>-<shortsha>.md (see spec §7), "
               "then re-run.")
        return
    records = sorted(adir.glob("APPROVAL-*.md"))
    if not records:
        report("approval", "AWAITING_APPROVAL",
               "HIGH change with no approval record in "
               f"{adir}. Resolution: obtain founder approval and add "
               "harness/APPROVAL-<date>-<shortsha>.md (see spec §7), "
               "then re-run.")
        return
    reasons = []
    for path in records:
        rec = _parse_approval_record(path)
        valid, reason = _validate_approval_record(rec, diff_sha, head_sha,
                                                  repo_dir)
        if valid:
            report("approval", "PASS",
                   f"HIGH change APPROVED — record {path.name} verified "
                   f"({reason}; tier HIGH, diff hash matches, "
                   f"approved {rec['approved-date']}). The change may "
                   "proceed.")
            return
        reasons.append(f"{path.name}: {reason}")
    report("approval", "AWAITING_APPROVAL",
           "HIGH change with no VALID approval record. "
           + "; ".join(reasons)
           + ". Resolution: obtain founder approval and add/correct "
           "harness/APPROVAL-<date>-<shortsha>.md (see spec §7), "
           "then re-run.")

# ---------------------------------------------------------------- main
class _Parser(argparse.ArgumentParser):
    """argparse exits 2 on usage errors by default — but exit 2 means
    AWAITING_APPROVAL in this script (Finding 4). Usage errors exit 3."""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(3)


def main(argv=None):
    ap = _Parser(description="Harness checks v1.1 for popaurmaa.com "
                             "(read-only).")
    ap.add_argument("--live", action="store_true", default=True,
                    help="fetch the live site (default)")
    ap.add_argument("--html", metavar="PATH",
                    help="check a local HTML file instead of the live site")
    ap.add_argument("--repo-dir", metavar="DIR",
                    help="local copy of the repo (secret scan, stubs, "
                         "site-config.js links, relative assets)")
    ap.add_argument("--diff", nargs=2, metavar=("OLD", "NEW"),
                    help="scope-guard: classify the change between two files")
    ap.add_argument("--diff-file", metavar="PATH",
                    help="scope-guard: classify a unified diff file "
                         "(multi-file; what CI passes)")
    ap.add_argument("--base-sha", metavar="SHA",
                    help="base commit SHA (approval verification)")
    ap.add_argument("--head-sha", metavar="SHA",
                    help="HEAD commit SHA (approval verification, revert "
                         "command)")
    ap.add_argument("--approval-dir", metavar="DIR",
                    help="directory holding harness/APPROVAL-*.md records "
                         "(default: <repo-dir>/harness)")
    ap.add_argument("--expect", metavar="MARKER",
                    help="post-deploy verify: marker that must be in live HTML")
    args = ap.parse_args(argv)

    if args.diff and args.diff_file:
        ap.error("--diff and --diff-file are mutually exclusive")

    html = None
    parser = None
    from_live = False
    if args.html:
        try:
            html = Path(args.html).read_text(encoding="utf-8")
        except OSError as exc:
            report("live_http", "FAIL", f"cannot read {args.html}: {exc}")
        else:
            report("live_http", "PASS",
                   f"local file {args.html} read "
                   f"({len(html.encode())} bytes); live fetch skipped")
            parser = check_required_tags(html)
            check_metadata_consistency(parser)
            check_internal_anchors(parser)
            check_external_links(html, args.repo_dir)
            check_relative_assets(parser, args.repo_dir, from_live=False)
    else:
        html = check_live_fetch()
        parser = check_required_tags(html)
        check_metadata_consistency(parser)
        check_internal_anchors(parser)
        check_external_links(html, args.repo_dir)
        check_relative_assets(parser, args.repo_dir, from_live=True)

    check_secret_scan(args.repo_dir)
    check_redirect_stubs(args.repo_dir)

    tier = None
    diff_sha = None
    if args.diff_file:
        tier, diff_sha = classify_diff_file(args.diff_file)
    elif args.diff:
        tier, diff_sha = classify_diff(args.diff[0], args.diff[1])
    else:
        report("scope_guard", "NOT RUN",
               "no --diff/--diff-file given; pass a change to classify it")

    check_approval(tier, diff_sha, args.base_sha, args.head_sha,
                   args.repo_dir, args.approval_dir)

    if args.expect is not None:
        post_deploy_verify(args.expect, args.head_sha)
    else:
        report("post_deploy_verify", "NOT RUN",
               "no --expect marker given; run after a deploy to confirm "
               "the change is live")

    print("popaurmaa.com harness checks v1.1")
    print("=" * 60)
    counts = {"PASS": 0, "FAIL": 0, "NOT RUN": 0, "AWAITING_APPROVAL": 0}
    for name, status, detail in RESULTS:
        print(f"[{status:17}] {name}: {detail}")
        counts[status] += 1
    print("=" * 60)
    print(f"{len(RESULTS)} checks: {counts['PASS']} PASS, "
          f"{counts['FAIL']} FAIL, {counts['NOT RUN']} NOT RUN, "
          f"{counts['AWAITING_APPROVAL']} AWAITING_APPROVAL")
    if counts["FAIL"]:
        print("RESULT: FAIL (exit 1) — a security check failed. The change "
              "is unsafe: fix the change itself. Never edit this script "
              "to make it pass, and no approval record can override a "
              "failed check.")
        return 1
    if counts["AWAITING_APPROVAL"]:
        print("RESULT: AWAITING_APPROVAL (exit 2) — security checks passed, "
              "but a HIGH-tier change has no valid approval record. The "
              "change is safe but not yet authorized: obtain founder "
              "approval, add harness/APPROVAL-<date>-<shortsha>.md, and "
              "re-run. Merging stays blocked.")
        return 2
    approval = next((s for n, s, _ in RESULTS if n == "approval"),
                    "NOT RUN")
    if approval == "PASS":
        print("RESULT: PASS / APPROVED (exit 0) — checks passed; a HIGH "
              "change had a valid approval record.")
    else:
        print("RESULT: PASS (exit 0) — checks passed; no approval record "
              "was required for this run.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
