#!/usr/bin/env python3
"""
full_audit.py — mechanical audit of jazzvinylguide album guides.

This script replaces "Claude says it's audited" with something you can run
yourself and verify independently. It checks everything that CAN be checked
mechanically (no judgment calls). It does NOT replace fact-checking prose
content (recording dates, personnel, mastering credits) — that still requires
a human or an LLM reading the source and comparing it against the guide.

WHAT THIS CHECKS
  1. Format conventions
     - Em-dashes (—) must be zero (n-dashes only)
     - No discogs.com/master/ links inside tier-table rows
     - No hyperlinks inside the Cat# column of the tier table
     - Summary section has at most 2 paragraphs before the "Best early
       pressing" bullets
  2. Tier table integrity
     - Tier order is non-decreasing (S, A, B, C, D, F — no S appearing
       after an A, etc.)
     - Duplicate Cat# values are flagged (informational — some are
       legitimate reissues sharing a catalog number, so this is a
       "look at this" flag, not an automatic failure)
  3. Buyer's guide integrity
     - Price bands are in strict, non-decreasing order
  4. Discogs link verification (REQUIRES INTERNET ACCESS TO discogs.com)
     - Extracts every discogs.com/release/N and discogs.com/master/N link
     - Fetches each one and confirms it resolves (HTTP 200, not a
       redirect to a search page or an error page)
     - NOTE: this only checks the link is ALIVE and resolves to a real
       release page. It cannot confirm the release page's content
       actually matches the claim next to it in the guide (mono vs
       stereo, correct year, etc.) — that step still needs a human or
       an LLM to read and compare. Treat a "link resolves" pass as
       necessary, not sufficient.
  5. albums.json cross-check
     - mbid is present and is a syntactically valid UUID
     - content_file matches an actual file in _content/
     - cover_url does not point at Wikipedia (per project convention)

WHAT THIS DOES NOT CHECK (still needs a human/LLM pass)
  - Whether facts (dates, personnel, mastering engineer, catalog numbers)
    are actually correct
  - Whether a linked Discogs release actually matches the claim made
    about it (format, year, pressing plant) — only that the link is alive
  - Whether the reissue hierarchy is complete (missing AP/Music
    Matters/Tone Poet/Speakers Corner/Japanese pressings, etc.)
  - Whether something is on the TAS Super LP List or Steve Hoffman forums

USAGE
    python3 scripts/full_audit.py                  # audit every guide
    python3 scripts/full_audit.py karma milestones  # audit specific slugs
    python3 scripts/full_audit.py --no-network      # skip live link checks

Exit code is 0 if everything passes, 1 if any guide has a failure.
"""

import sys
import os
import re
import json
import argparse
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(ROOT, "_content")
ALBUMS_JSON = os.path.join(ROOT, "albums.json")

TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3, "D": 4, "F": 5}
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I
)
DISCOGS_LINK_RE = re.compile(r"discogs\.com/(release|master)/(\d+)")
MASTER_LINK_RE = re.compile(r"discogs\.com/master/\d+")
PRICE_RE = re.compile(r"\$([\d,]+)")


class Result:
    def __init__(self, slug):
        self.slug = slug
        self.errors = []
        self.warnings = []
        self.info = []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.info.append(msg)

    @property
    def passed(self):
        return not self.errors


def load_albums():
    with open(ALBUMS_JSON) as f:
        return json.load(f)


def check_em_dashes(content, r):
    count = content.count("\u2014")
    if count > 0:
        r.error(f"{count} em-dash(es) found (n-dashes only per convention)")


def extract_tier_rows(content):
    if "## Pressing tier summary" not in content:
        return []
    tier_section = content.split("## Pressing tier summary")[1]
    return [l for l in tier_section.split("\n") if l.strip().startswith("| **")]


def check_master_links_in_tiers(rows, r):
    for row in rows:
        if MASTER_LINK_RE.search(row):
            r.error(f"master-page link used in a tier row (should be a specific release): {row[:90]}...")


def check_catno_hyperlinks(rows, r):
    for row in rows:
        cols = row.split("|")
        if len(cols) > 3:
            catno = cols[3].strip()
            if "[" in catno or "http" in catno:
                r.error(f"hyperlink found inside Cat# column: {row[:90]}...")


def check_tier_order(rows, r):
    tiers = []
    for row in rows:
        cols = row.split("|")
        if len(cols) > 2:
            tier = cols[2].strip().replace("*", "")
            tiers.append(tier)
    ranks = [TIER_ORDER.get(t, 99) for t in tiers]
    if ranks != sorted(ranks):
        r.error(f"tier order is not non-decreasing: {tiers}")
    else:
        r.note(f"tier order OK: {tiers}")


def check_duplicate_catnos(rows, r):
    cats = []
    for row in rows:
        cols = row.split("|")
        if len(cols) > 3:
            cats.append(cols[3].strip())
    seen = {}
    for c in cats:
        if c in ("\u2013", "-", ""):
            continue
        seen[c] = seen.get(c, 0) + 1
    dupes = [c for c, n in seen.items() if n > 1]
    if dupes:
        r.warn(f"duplicate Cat# values (verify these are genuinely distinct pressings): {dupes}")


def check_summary_paragraphs(content, r):
    if "## Summary" not in content or "## Recording history" not in content:
        r.warn("could not locate Summary/Recording history sections to check paragraph count")
        return
    summary = content.split("## Summary")[1].split("## Recording history")[0]
    if "**Best early pressing" in summary:
        prose = summary.split("**Best early pressing")[0].strip()
    else:
        prose = summary.strip()
    paras = [p for p in prose.split("\n\n") if p.strip()]
    if len(paras) > 2:
        r.error(f"Summary has {len(paras)} paragraphs before the bullets (max 2 allowed)")


def check_buyers_guide_order(content, r):
    if "## Buyer's guide" not in content:
        r.warn("no Buyer's guide section found")
        return
    section = content.split("## Buyer's guide")[1]
    if "## Pressing tier" in section:
        section = section.split("## Pressing tier")[0]
    # New system: headers use a relative $ .. $$$$$ symbol scale, e.g. "**$$$ (Mid-range):**",
    # rather than absolute dollar figures. Check the symbol-count sequence is non-decreasing.
    header_re = re.compile(r'^\*\*(\${1,5})\s*\(')
    lines = [l for l in section.split("\n") if l.strip().startswith("**")]
    band_counts = []
    for l in lines:
        m = header_re.match(l.strip())
        if m:
            band_counts.append(len(m.group(1)))
    if band_counts and band_counts != sorted(band_counts):
        r.error(f"buyer's guide price bands not in ascending order: {band_counts}")
    elif band_counts:
        r.note(f"buyer's guide order OK: {band_counts}")


def check_links(content, r, do_network):
    links = sorted(set(DISCOGS_LINK_RE.findall(content)), key=lambda x: x[1])
    if not links:
        r.warn("no Discogs links found in this guide")
        return
    r.note(f"{len(links)} unique Discogs link(s) found")
    if not do_network:
        r.note("network link-check skipped (--no-network or unreachable)")
        return
    for kind, num in links:
        url = f"https://www.discogs.com/{kind}/{num}"
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            resp = urlopen(req, timeout=10)
            code = resp.getcode()
            if code != 200:
                r.error(f"{kind}/{num} returned HTTP {code}")
        except HTTPError as e:
            r.error(f"{kind}/{num} returned HTTP {e.code} (dead or moved link)")
        except URLError as e:
            r.warn(f"{kind}/{num} could not be reached ({e.reason}) — network may be unavailable")
        time.sleep(0.5)  # be polite


def check_albums_json_entry(slug, entry, r):
    mbid = entry.get("mbid", "")
    if mbid == "":
        r.warn("mbid is blank")
    elif not UUID_RE.match(mbid):
        r.error(f"mbid is not a syntactically valid UUID: {mbid!r}")

    content_file = entry.get("content_file", "")
    path = os.path.join(CONTENT_DIR, content_file)
    if not content_file:
        r.error("content_file field is missing from albums.json")
    elif not os.path.isfile(path):
        r.error(f"content_file {content_file!r} does not exist in _content/")

    cover_url = entry.get("cover_url", "")
    if "wikipedia" in cover_url.lower():
        r.error(f"cover_url points at Wikipedia, not allowed: {cover_url}")


def audit_one(slug, entry, do_network):
    r = Result(slug)
    path = os.path.join(CONTENT_DIR, entry["content_file"])
    if not os.path.isfile(path):
        r.error(f"content file not found: {path}")
        return r

    with open(path) as f:
        content = f.read()

    if len(content.strip()) < 200:
        r.warn("file looks like it may still be a stub (<200 chars)")
        return r

    check_em_dashes(content, r)
    check_summary_paragraphs(content, r)
    rows = extract_tier_rows(content)
    if not rows:
        r.error("no tier table rows found")
    else:
        check_master_links_in_tiers(rows, r)
        check_catno_hyperlinks(rows, r)
        check_tier_order(rows, r)
        check_duplicate_catnos(rows, r)
    check_buyers_guide_order(content, r)
    check_links(content, r, do_network)
    check_albums_json_entry(slug, entry, r)

    return r


def network_available():
    try:
        urlopen(Request("https://www.discogs.com/", headers={"User-Agent": "Mozilla/5.0"}), timeout=5)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Mechanical audit of album guides.")
    parser.add_argument("slugs", nargs="*", help="specific slugs to audit (default: all)")
    parser.add_argument("--no-network", action="store_true", help="skip live Discogs link checks")
    args = parser.parse_args()

    albums = load_albums()
    by_slug = {a["slug"]: a for a in albums}

    targets = args.slugs if args.slugs else list(by_slug.keys())

    do_network = not args.no_network
    if do_network and not network_available():
        print("NOTE: discogs.com is not reachable from this environment.")
        print("Link-liveness checks will be skipped. Run this script from an")
        print("environment with normal internet access (e.g. your own terminal,")
        print("not Claude's sandboxed tool environment) to run them for real.\n")
        do_network = False

    results = []
    for slug in targets:
        if slug not in by_slug:
            print(f"!! unknown slug: {slug}")
            continue
        r = audit_one(slug, by_slug[slug], do_network)
        results.append(r)

    print(f"{'SLUG':35} {'STATUS':8} ERRORS / WARNINGS")
    print("-" * 100)
    any_failed = False
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        if not r.passed:
            any_failed = True
        print(f"{r.slug:35} {status:8}")
        for e in r.errors:
            print(f"    ERROR:   {e}")
        for w in r.warnings:
            print(f"    warning: {w}")

    print("-" * 100)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    print(f"{passed}/{total} guides passed mechanical audit.")
    if not do_network:
        print("Link-liveness was NOT checked this run (no network access to discogs.com).")

    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
