#!/usr/bin/env python3
"""
Jazz Vinyl Guide — Discogs Market Data Fetcher

Pulls, per pressing linked in a guide's tier table:
  - num_for_sale + lowest_price for the release OVERALL, via
    /marketplace/stats/{release_id}?curr_abbr=... (the endpoint explicitly
    documented as returning currency-scoped "marketplace data" -- earlier,
    this script pulled these two fields from /releases/{id} instead, passing
    the same curr_abbr param; a live run requesting USD came back with a
    number that matched the AUD-converted price instead, meaning curr_abbr's
    effect on that particular field of that particular endpoint wasn't
    reliable in practice, whatever the docs imply. Switched to the endpoint
    whose sole purpose is currency-scoped marketplace stats, and this script
    now also verifies the currency actually returned matches what was asked
    for, logging a loud warning if it ever doesn't rather than silently
    mislabeling again.)
  - suggested_price PER CONDITION (Mint, NM, VG+, VG, Good), via
    /marketplace/price_suggestions/{release_id}, same verification applied.

IMPORTANT, corrected after v1 shipped bad data: Discogs' marketplace/stats
endpoint does NOT support a per-condition filter. v1 of this script passed a
`condition` query param to /marketplace/stats/{id} believing it would return
for_sale/lowest_price scoped to that condition -- it does not. That parameter
belongs to a completely different endpoint (creating a marketplace listing),
and the stats endpoint silently ignored it, returning the same release-wide
numbers on every call regardless of which condition was requested. The result
was 5 near-identical calls per release for nothing, and a widget showing a
distinct "for sale" count under every dot that was actually just the same
release-wide number, duplicated -- implying a precision the API can't back up.

The only thing Discogs actually varies by condition is price_suggestions.
for_sale and lowest_price only ever exist release-wide. This version reflects
that honestly: one for_sale/lowest_price pair per release, one suggested_price
per condition. Confirmed against the documented parameters for both endpoints
before rewriting this.

Median, average, and highest price remain unavailable via the API entirely
(only ever shown on the login-gated /sell/history/ page) -- unchanged from v1.

Output: a single JSON sidecar (market_data.json) at the repo root, keyed by
Discogs release_id, e.g.:

{
  "24373778": {
    "fetched_at": "2026-07-16T09:12:00Z",
    "currency": "USD",
    "for_sale": 6,
    "lowest_price": 215.0,
    "suggested_prices": {
      "Good (G)":             12.4,
      "Very Good (VG)":       85.1,
      "Very Good Plus (VG+)": 215.0,
      "Near Mint (NM or M-)": 260.1,
      "Mint (M)":             340.5
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

# Discogs' 5 collector-relevant conditions, in low-to-high order (matches the
# dot ladder in the tier-table widget). "Fair" and "Poor" are excluded --
# collector-grade guides don't quote prices at that grade, and Gemini/audit
# conventions never reference them either. This order only ever applies to
# suggested_prices now -- for_sale/lowest_price are release-wide, not per
# condition, per the correction above.
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
    parsed JSON, or None on a 404."""
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
    Returns a dict of release_id -> list of slugs, for traceability, since one
    release can legitimately appear in more than one guide's table (rare, but
    happens with box sets covering two albums)."""
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
    """One release -> release-wide for_sale + lowest_price (via
    /marketplace/stats, which is explicitly documented as currency-scoped
    "marketplace data" -- unlike /releases/{id}, a general database resource
    where curr_abbr's effect on this particular field turned out to be
    unreliable in practice: a live run requesting USD returned a number that
    matched the AUD-converted price, not the USD one) plus per-condition
    suggested_price. Returns None if the release doesn't resolve at all."""

    stats = discogs_get(f"/marketplace/stats/{release_id}", params={"curr_abbr": currency})
    time.sleep(REQUEST_DELAY)

    if stats is None:
        # No stats (e.g. zero listings ever) isn't necessarily a dead link --
        # confirm the release itself still exists before flagging it stale.
        base = discogs_get(f"/releases/{release_id}")
        time.sleep(REQUEST_DELAY)
        if base is None:
            return None
        for_sale, lowest_price, actual_currency = 0, None, currency
    else:
        for_sale = stats.get("num_for_sale") or 0
        lowest = stats.get("lowest_price")
        if isinstance(lowest, dict):
            lowest_price = lowest.get("value")
            actual_currency = lowest.get("currency", currency)
        else:
            lowest_price = lowest
            actual_currency = currency

    if actual_currency != currency:
        print(f"\n        WARNING: requested {currency} but Discogs returned {actual_currency} "
              f"for release {release_id} -- stored value is in {actual_currency}, not {currency}.")

    suggested_prices = {c: None for c in CONDITIONS}
    suggestions = discogs_get(f"/marketplace/price_suggestions/{release_id}")
    time.sleep(REQUEST_DELAY)
    if suggestions:
        for condition in CONDITIONS:
            entry = suggestions.get(condition)
            if entry:
                suggested_prices[condition] = round(entry.get("value", 0), 2)
                sugg_currency = entry.get("currency", currency)
                if sugg_currency != currency:
                    print(f"\n        WARNING: price_suggestions for {release_id}/{condition} "
                          f"came back in {sugg_currency}, not requested {currency}.")

    return {
        "for_sale": for_sale,
        "lowest_price": lowest_price,
        "currency": actual_currency,
        "suggested_prices": suggested_prices,
    }


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
        est_calls = len(found) * 2  # 1 release lookup (incl. for_sale/lowest_price) + 1 suggestions
        est_minutes = (est_calls * REQUEST_DELAY) / 60
        print(f"\nEstimated API calls for --all: {est_calls} (~{est_minutes:.0f} min at {REQUEST_DELAY}s/call)")
        return

    if not DISCOGS_TOKEN:
        print("ERROR: Set DISCOGS_TOKEN environment variable (Discogs Settings -> Developers -> Generate new token)")
        sys.exit(1)

    if args.release:
        print(f"Fetching {args.release}...")
        data = fetch_release_market_data(args.release, currency=args.currency)
        if data is None:
            print("  release_id not found on Discogs")
            return
        print(json.dumps(data, indent=2))
        return

    if args.all:
        found = scan_release_ids()
        print(f"Fetching market data for {len(found)} releases (currency={args.currency})...")
        result = {}
        stale = []

        for i, (release_id, slugs) in enumerate(sorted(found.items()), 1):
            print(f"  [{i}/{len(found)}] {release_id} ({', '.join(slugs)})...", end=" ")
            try:
                data = fetch_release_market_data(release_id, currency=args.currency)
            except Exception as e:
                print(f"ERROR: {e}")
                continue

            if data is None:
                print("NOT FOUND — link may be stale, flagging for manual check")
                stale.append({"release_id": release_id, "guides": slugs})
                continue

            print(f"{data['for_sale']} for sale overall, from {data['currency']} {data['lowest_price']}")

            result[release_id] = {
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "currency": args.currency,
                **data,
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
