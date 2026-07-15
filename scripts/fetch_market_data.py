#!/usr/bin/env python3
"""
Jazz Vinyl Guide — Discogs Market Data Fetcher

Pulls, per pressing linked in a guide's tier table:
  - num_for_sale + lowest_price, per condition (Mint, NM, VG+, VG, Good)
    via /marketplace/stats/{release_id}?curr_abbr=...&condition=...
  - suggested price, per condition, via /marketplace/price_suggestions/{release_id}
    (requires OAuth — a personal access token is enough, no app registration)

Discogs does NOT expose median, average, or highest price via the API (confirmed
against the API docs and multiple developer-forum threads — only ever available
on the login-gated /sell/history/ page, out of scope for this pipeline). So this
script only ever writes num_for_sale, lowest_price, and price_suggestions.

Output: a single JSON sidecar (market_data.json) at the repo root, keyed by
Discogs release_id, e.g.:

{
  "24373778": {
    "fetched_at": "2026-07-15T09:12:00Z",
    "currency": "AUD",
    "conditions": {
      "Mint (M)":            {"for_sale": 2, "lowest_price": 298.0, "suggested_price": 340.5},
      "Near Mint (NM or M-)": {"for_sale": 3, "lowest_price": 210.0, "suggested_price": 260.1},
      "Very Good Plus (VG+)":{"for_sale": 1, "lowest_price": 215.0, "suggested_price": 215.0},
      "Very Good (VG)":      {"for_sale": 0, "lowest_price": null,  "suggested_price": null},
      "Good (G)":            {"for_sale": 0, "lowest_price": null,  "suggested_price": null}
    }
  },
  ...
}

build.py reads this sidecar at render time to draw the market widget. This
script never touches _content/*.md and never pushes to GitHub — it only
produces market_data.json for you to review and commit like any other file.

Usage:
    python3 fetch_market_data.py --scan                     # list every release_id found in _content/, no API calls
    python3 fetch_market_data.py --all                       # fetch all releases, write market_data.json
    python3 fetch_market_data.py --release 24373778          # fetch a single release (debugging)
    python3 fetch_market_data.py --all --currency AUD
    python3 fetch_market_data.py --all --dry-run             # fetch but don't write the file, just print
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

DISCOGS_TOKEN = os.environ.get("DISCOGS_TOKEN", "")
CONTENT_DIR = "_content"
OUTPUT_FILE = "market_data.json"

USER_AGENT = "JazzVinylGuideBot/1.0 +https://jazzvinylguide.com"

# Discogs' 8 standard conditions, in low-to-high order (matches the dot ladder
# in the tier-table widget). "Fair" and "Poor" are excluded — collector-grade
# guides don't quote prices at that grade, and Gemini/audit conventions never
# reference them either.
CONDITIONS = [
    "Good (G)",
    "Very Good (VG)",
    "Very Good Plus (VG+)",
    "Near Mint (NM or M-)",
    "Mint (M)",
]

# Discogs rate limit: 60 req/min authenticated. We stay under that with a
# fixed delay rather than trying to track a rolling window — simpler, and
# the wall-clock cost is the same either way for a batch job like this.
REQUEST_DELAY = 1.1  # seconds between requests (~54/min, safety margin)

RELEASE_LINK_RE = re.compile(r"discogs\.com/release/(\d+)")


def discogs_get(path, params=None):
    """GET against api.discogs.com with the personal access token. Returns
    parsed JSON, or None on a 404 (release exists but nothing for that
    condition is unusual but not an error — treat as zero listings)."""
    url = f"https://api.discogs.com{path}"
    if params:
        query = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
        url = f"{url}?{query}"

    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Authorization": f"Discogs token={DISCOGS_TOKEN}",
    })

    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429:
            print("        429 rate limited — waiting 60s...")
            time.sleep(60)
            return discogs_get(path, params)
        body = e.read().decode(errors="replace")
        raise Exception(f"Discogs HTTP {e.code} for {url}: {body[:200]}")


def scan_release_ids():
    """Pull every Discogs release_id referenced in _content/*.md tier tables.
    Returns a dict of release_id -> list of (slug, pressing name) for
    traceability, since one release can legitimately appear in more than one
    guide's table (rare, but happens with box sets covering two albums)."""
    if not os.path.isdir(CONTENT_DIR):
        print(f"ERROR: {CONTENT_DIR}/ not found. Run this from the repo root.")
        sys.exit(1)

    found = {}
    for filename in sorted(os.listdir(CONTENT_DIR)):
        if not filename.endswith(".md"):
            continue
        slug = filename.replace("_vinyl_guide.md", "").replace(".md", "")
        with open(os.path.join(CONTENT_DIR, filename)) as f:
            text = f.read()
        for match in RELEASE_LINK_RE.finditer(text):
            release_id = match.group(1)
            found.setdefault(release_id, []).append(slug)

    return found


def fetch_release_market_data(release_id, currency="USD"):
    """One release -> per-condition for_sale + lowest_price (5 stats calls)
    plus one price_suggestions call. Returns the conditions dict, or None if
    the release_id itself doesn't resolve (bad/stale link — flag, don't fetch)."""

    base = discogs_get(f"/releases/{release_id}")
    time.sleep(REQUEST_DELAY)
    if base is None:
        return None

    conditions = {c: {"for_sale": 0, "lowest_price": None, "suggested_price": None} for c in CONDITIONS}

    for condition in CONDITIONS:
        stats = discogs_get(
            f"/marketplace/stats/{release_id}",
            params={"curr_abbr": currency, "condition": condition},
        )
        time.sleep(REQUEST_DELAY)
        if stats:
            conditions[condition]["for_sale"] = stats.get("num_for_sale") or 0
            lowest = stats.get("lowest_price")
            if lowest:
                conditions[condition]["lowest_price"] = lowest.get("value")

    suggestions = discogs_get(f"/marketplace/price_suggestions/{release_id}")
    time.sleep(REQUEST_DELAY)
    if suggestions:
        for condition in CONDITIONS:
            entry = suggestions.get(condition)
            if entry:
                conditions[condition]["suggested_price"] = round(entry.get("value", 0), 2)

    return conditions


def main():
    parser = argparse.ArgumentParser(description="Fetch Discogs market data for all linked pressings")
    parser.add_argument("--scan", action="store_true", help="List release_ids found in _content/, no API calls")
    parser.add_argument("--all", action="store_true", help="Fetch market data for every release_id found")
    parser.add_argument("--release", help="Fetch a single release_id (debugging)")
    parser.add_argument("--currency", default="USD", help="Currency for prices (default USD)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print, but don't write market_data.json")
    args = parser.parse_args()

    if args.scan:
        found = scan_release_ids()
        print(f"Found {len(found)} unique release_ids across _content/:")
        for release_id, slugs in sorted(found.items(), key=lambda kv: kv[1]):
            print(f"  {release_id:>10}  <- {', '.join(slugs)}")
        est_calls = len(found) * 7  # 1 release lookup + 5 stats + 1 suggestions
        est_minutes = (est_calls * REQUEST_DELAY) / 60
        print(f"\nEstimated API calls for --all: {est_calls} (~{est_minutes:.0f} min at {REQUEST_DELAY}s/call)")
        return

    if not DISCOGS_TOKEN:
        print("ERROR: Set DISCOGS_TOKEN environment variable (Discogs Settings -> Developers -> Generate new token)")
        sys.exit(1)

    if args.release:
        print(f"Fetching {args.release}...")
        conditions = fetch_release_market_data(args.release, currency=args.currency)
        if conditions is None:
            print("  release_id not found on Discogs")
            return
        print(json.dumps(conditions, indent=2))
        return

    if args.all:
        found = scan_release_ids()
        print(f"Fetching market data for {len(found)} releases (currency={args.currency})...")
        result = {}
        stale = []

        for i, (release_id, slugs) in enumerate(sorted(found.items()), 1):
            print(f"  [{i}/{len(found)}] {release_id} ({', '.join(slugs)})...", end=" ")
            try:
                conditions = fetch_release_market_data(release_id, currency=args.currency)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            if conditions is None:
                print("NOT FOUND — link may be stale, flagging for manual check")
                stale.append({"release_id": release_id, "guides": slugs})
                continue

            total_for_sale = sum(c["for_sale"] for c in conditions.values())
            print(f"{total_for_sale} listings across all conditions")

            result[release_id] = {
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "currency": args.currency,
                "conditions": conditions,
            }

        print(f"\nDone: {len(result)} releases fetched, {len(stale)} stale/not-found")

        if stale:
            print("\nStale release links (recommend a manual audit pass, not auto-removal):")
            for s in stale:
                print(f"  {s['release_id']} <- {', '.join(s['guides'])}")

        if args.dry_run:
            print("\n--dry-run set: not writing market_data.json. Sample output:")
            sample_key = next(iter(result), None)
            if sample_key:
                print(json.dumps({sample_key: result[sample_key]}, indent=2))
            return

        with open(OUTPUT_FILE, "w") as f:
            json.dump(result, f, indent=2, sort_keys=True)
        print(f"\nWritten to {OUTPUT_FILE} — review and commit like any other file.")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
