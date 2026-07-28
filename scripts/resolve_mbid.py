#!/usr/bin/env python3
"""
Jazz Vinyl Guide — MusicBrainz Release-Group Resolver

Why this exists: eight guides went into albums.json in a single research
session with mbid left blank on all of them "for follow-up." That follow-up
never had a dedicated tool, so it depended on someone remembering to do it
by hand next time -- which is exactly the kind of step that quietly gets
skipped under time pressure. This script makes MusicBrainz lookup a single
command instead of a manual research task, so there's no reason for a blank
mbid to survive past the session that created it.

What it does:
  - Reads albums.json, finds every entry with mbid == "" (the site's
    established convention for "intentionally blank, not yet confirmed" --
    see HANDOFF.md and the Complete Savoy and Dial entry).
  - Queries the MusicBrainz release-group search API
    (https://musicbrainz.org/ws/2/release-group) for each, using artist +
    title.
  - A match is only auto-applied if the API's own relevance score is >= 95
    AND the returned artist-credit name matches (case-insensitive) the
    artist field already in albums.json. Anything less confident is
    printed for manual review and left blank -- this mirrors the site's
    own "never fabricate, leave blank and flag if uncertain" rule for
    mbid, just applied to the lookup step instead of the writing step.
  - Dry-run by default (prints what it would change). Pass --write to
    actually update albums.json.

MusicBrainz API etiquette (both enforced here, not optional):
  - Requires a descriptive User-Agent identifying the application, per
    https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting -- requests
    without one are more likely to be rate-limited or blocked outright.
  - Rate limit: max ~1 request/second for unauthenticated use. This script
    sleeps between requests accordingly; do not remove that sleep or lower
    it, or the whole batch risks getting throttled or blocked mid-run.

Network note: musicbrainz.org is not reachable from every environment this
repo gets worked on in (e.g. Claude's sandboxed bash tool cannot reach it,
same restriction that already applies to discogs.com). Run this from an
environment with open internet access -- a local machine, or via the
companion GitHub Actions workflow (resolve_mbid.yml, workflow_dispatch),
which runs on a GitHub-hosted runner with full internet access, the same
pattern already used by fetch_market_data.py / market_data.yml.

Usage:
    python3 scripts/resolve_mbid.py                # dry run, all blank mbids
    python3 scripts/resolve_mbid.py --write         # apply confident matches
    python3 scripts/resolve_mbid.py --slug red-clay # single album, dry run
"""

import argparse
import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

ALBUMS_JSON = "albums.json"
MB_SEARCH_URL = "https://musicbrainz.org/ws/2/release-group/"
USER_AGENT = "JazzVinylGuide-MBIDResolver/1.0 (https://jazzvinylguide.com)"
MIN_SCORE = 95
REQUEST_DELAY_SECONDS = 1.1  # MusicBrainz asks for max ~1 req/sec; pad slightly


def mb_search_release_group(artist, title):
    """
    Query MusicBrainz release-group search. Returns the raw list of
    candidate results (possibly empty), each a dict with at least
    'id', 'score', 'title', and 'artist-credit'.
    """
    query = f'artist:"{artist}" AND releasegroup:"{title}"'
    params = urllib.parse.urlencode({"query": query, "fmt": "json", "limit": 5})
    url = f"{MB_SEARCH_URL}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get("release-groups", [])
    except urllib.error.HTTPError as e:
        print(f"        HTTP {e.code} querying MusicBrainz for {artist!r} / {title!r}")
        return []
    except urllib.error.URLError as e:
        print(f"        Network error querying MusicBrainz: {e.reason}")
        return []


def best_match(candidates, expected_artist):
    """
    Return (mbid, title, score) for the best candidate that meets the
    confidence bar, or None if nothing qualifies. Confidence bar:
    MusicBrainz relevance score >= MIN_SCORE AND the artist-credit name
    matches expected_artist case-insensitively (avoids confidently
    attaching the mbid of a same-titled album by a different artist).
    """
    expected_lower = expected_artist.strip().lower()
    for c in candidates:
        score = int(c.get("score", 0))
        if score < MIN_SCORE:
            continue
        credits = c.get("artist-credit", [])
        names = [ac.get("name", "").strip().lower() for ac in credits if isinstance(ac, dict)]
        if expected_lower in names or any(expected_lower in n or n in expected_lower for n in names):
            return c["id"], c.get("title", ""), score
    return None


def main():
    parser = argparse.ArgumentParser(description="Resolve blank MusicBrainz release-group IDs in albums.json")
    parser.add_argument("--write", action="store_true", help="Apply confident matches to albums.json (default: dry run)")
    parser.add_argument("--slug", help="Only process this one album slug")
    args = parser.parse_args()

    with open(ALBUMS_JSON) as f:
        albums = json.load(f)

    targets = [a for a in albums if a.get("mbid", "") == ""]
    if args.slug:
        targets = [a for a in targets if a["slug"] == args.slug]
        if not targets:
            print(f"No blank-mbid album found with slug {args.slug!r} (already resolved, or slug doesn't exist).")
            return

    if not targets:
        print("No blank mbid fields found -- nothing to do.")
        return

    print(f"{len(targets)} album(s) with blank mbid. Querying MusicBrainz (rate-limited to ~1 req/sec)...\n")

    resolved = []
    needs_review = []

    for i, album in enumerate(targets):
        artist, title, slug = album["artist"], album["title"], album["slug"]
        print(f"  [{slug}] {artist} - {title}")
        candidates = mb_search_release_group(artist, title)
        match = best_match(candidates, artist)

        if match:
            mbid, mb_title, score = match
            print(f"        MATCH  score={score}  mbid={mbid}  (MusicBrainz title: {mb_title!r})")
            resolved.append((slug, mbid))
        else:
            top = candidates[0] if candidates else None
            if top:
                top_names = ", ".join(ac.get("name", "?") for ac in top.get("artist-credit", []) if isinstance(ac, dict))
                print(f"        NO CONFIDENT MATCH -- top candidate: score={top.get('score')}, "
                      f"title={top.get('title')!r}, artist={top_names!r}, id={top.get('id')}")
            else:
                print("        NO CANDIDATES RETURNED")
            needs_review.append(slug)

        if i < len(targets) - 1:
            time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\n{'='*60}")
    print(f"  Resolved with high confidence: {len(resolved)}")
    print(f"  Needs manual review:           {len(needs_review)}")
    if needs_review:
        print(f"    -> {', '.join(needs_review)}")
        print("    These stay blank. Do not guess -- confirm manually on")
        print("    musicbrainz.org and add directly, same as any other")
        print("    manually-confirmed mbid on this site.")

    if not args.write:
        print("\nDry run (default) -- no changes written. Re-run with --write to apply.")
        return

    if not resolved:
        print("\nNothing to write.")
        return

    slug_to_mbid = dict(resolved)
    for a in albums:
        if a["slug"] in slug_to_mbid:
            a["mbid"] = slug_to_mbid[a["slug"]]

    with open(ALBUMS_JSON, "w") as f:
        json.dump(albums, f, indent=2)
        f.write("\n")

    print(f"\n--write set: applied {len(resolved)} mbid(s) to {ALBUMS_JSON}.")


if __name__ == "__main__":
    main()
