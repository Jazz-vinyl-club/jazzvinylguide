import json, os, urllib.request, urllib.parse, time

def search_mbid(title, artist):
    """Find MusicBrainz release group ID by searching title + artist."""
    query = urllib.parse.quote(f'"{title}" AND artist:"{artist}"')
    url = f"https://musicbrainz.org/ws/2/release-group?query={query}&type=album&fmt=json&limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "JazzVinylGuide/1.0 (jazzvinylguide.com)"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    groups = data.get("release-groups", [])
    if groups:
        return groups[0]["id"]
    return None

def download_cover(slug, mbid):
    dest = f"covers/{slug}.jpg"
    if os.path.exists(dest):
        print(f"  ✓ {slug}.jpg exists")
        return True
    url = f"https://coverartarchive.org/release-group/{mbid}/front-500"
    req = urllib.request.Request(url, headers={"User-Agent": "JazzVinylGuide/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = r.read()
    with open(dest, "wb") as f:
        f.write(data)
    print(f"  ✓ {slug}.jpg ({len(data)//1024}KB)")
    return True

os.makedirs("covers", exist_ok=True)
with open("albums.json") as f:
    albums = json.load(f)

for album in albums:
    slug   = album["slug"]
    title  = album["title"]
    artist = album["artist"]
    print(f"  → {slug}...")
    try:
        mbid = search_mbid(title, artist)
        if not mbid:
            print(f"  ✗ Not found on MusicBrainz")
            continue
        time.sleep(1)  # MusicBrainz rate limit: 1 request/second
        download_cover(slug, mbid)
    except Exception as e:
        print(f"  ✗ {e}")

print("\nDone.")
print("Next: git add covers/ && git commit -m 'Add covers' && git push")
print("Then: python3 build.py && git add -A && git commit -m 'Rebuild' && git push")
