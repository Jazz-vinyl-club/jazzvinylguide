#!/usr/bin/env python3
"""
Jazz Vinyl Guide — Site Builder
================================
Usage:
  python3 build.py              # build all albums
  python3 build.py slug         # rebuild one album e.g. python3 build.py kind-of-blue

To add a new album:
  1. Add entry to albums.json
  2. Add markdown guide to _content/
  3. Run python3 build.py <new-slug>
"""

import json
import os
import re
import sys
import urllib.request
import urllib.parse

try:
    import markdown
except ImportError:
    print("Installing markdown...")
    os.system("pip install markdown --break-system-packages -q")
    import markdown

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR  = os.path.join(BASE_DIR, "_content")
OUTPUT_DIR   = BASE_DIR
ALBUMS_FILE  = os.path.join(BASE_DIR, "albums.json")

# ── Wikipedia image fetcher ─────────────────────────────────────────────────
COVER_CACHE = {}  # slug -> img_url

def get_wikipedia_cover(wikipedia_title, slug):
    """Fetch cover image URL from Wikipedia API."""
    if slug in COVER_CACHE:
        return COVER_CACHE[slug]

    encoded = urllib.parse.quote(wikipedia_title)
    api_url = (
        f"https://en.wikipedia.org/w/api.php"
        f"?action=query&titles={encoded}"
        f"&prop=pageimages&format=json&pithumbsize=400"
        f"&pilicense=any"
    )
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "JazzVinylGuide/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        pages = data["query"]["pages"]
        page  = list(pages.values())[0]
        url   = page.get("thumbnail", {}).get("source", "")
        COVER_CACHE[slug] = url
        return url
    except Exception as e:
        print(f"  ⚠ Cover fetch failed for {slug}: {e}")
        return ""

# ── HTML helpers ────────────────────────────────────────────────────────────
GITHUB_BASE = "https://github.com/Jazz-vinyl-club/jazzvinylguide/edit/main/_content"

def site_header():
    return '''<header class="site-header">
  <div class="site-header__inner">
    <a class="site-logo" href="/">Jazz <span>Vinyl</span> Guide</a>
    <nav class="site-nav">
      <a href="/">Albums</a>
      <a href="/about.html">About</a>
      <a href="/contribute.html">Contribute</a>
    </nav>
  </div>
</header>'''

def site_footer():
    return '''<footer class="site-footer">
  <p><a href="https://jazzvinylguide.com">jazzvinylguide.com</a> — Collector-grade pressing guides for essential jazz albums. <a href="/contribute.html">Contribute an edit</a>.</p>
</footer>'''

def html_shell(title, description, body):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Jazz Vinyl Guide</title>
  <meta name="description" content="{description}">
  <meta property="og:title" content="{title} — Jazz Vinyl Guide">
  <meta property="og:description" content="{description}">
  <link rel="canonical" href="https://jazzvinylguide.com/">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
{site_header()}
<main>
{body}
</main>
{site_footer()}
<script src="/main.js"></script>
</body>
</html>'''

# ── Markdown → HTML ─────────────────────────────────────────────────────────
def md_to_html(md_text):
    # Strip H1 title line
    lines = md_text.split('\n')
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    # Strip subtitle italic line e.g. *Art Blakey...*
    if lines and re.match(r'^\*[^*]+\*\s*$', lines[0].strip()):
        lines = lines[1:]
    text = '\n'.join(lines)
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    return md.convert(text)

# ── Page builders ────────────────────────────────────────────────────────────
def build_index(albums):
    rows = ""
    for a in albums:
        rows += f'''    <a class="album-card" href="/albums/{a['slug']}.html">
      <h2 class="album-card__title">{a['title']}</h2>
      <p class="album-card__artist">{a['artist']}</p>
      <p class="album-card__meta">{a['label']} · {a['year']}</p>
      <span class="album-card__arrow">Read full guide →</span>
    </a>\n'''

    body = f'''<section class="hero">
  <h1 class="hero__title">Collector-grade guides for essential jazz albums</h1>
</section>
<section class="albums-section">
  <div class="album-grid">
{rows}  </div>
</section>'''

    html = html_shell(
        "Jazz Vinyl Guide",
        "Collector-grade vinyl pressing guides for essential jazz albums — recording history, pressing identification, reissue hierarchies, and buyer's guides.",
        body
    )
    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, 'w') as f:
        f.write(html)
    print(f"  ✓ index.html")

def build_album(album):
    slug   = album['slug']
    title  = album['title']
    artist = album['artist']
    label  = album['label']
    year   = album['year']

    # Load content
    content_path = os.path.join(CONTENT_DIR, album['content_file'])
    if not os.path.exists(content_path):
        print(f"  ⚠ Missing content: {content_path}")
        return
    with open(content_path, 'r') as f:
        md_text = f.read()
    content_html = md_to_html(md_text)

    # Cover image — use stored URL if available, else try Wikipedia API
    cover_url = album.get('cover_url', '')
    if not cover_url:
        print(f"  → Fetching cover for {title}...")
        cover_url = get_wikipedia_cover(album['wikipedia'], slug)
        if cover_url:
            # Cache back to album for future builds
            album['cover_url'] = cover_url
    if cover_url:
        cover_html = f'''    <figure class="album-header__cover">
      <img src="{cover_url}" alt="{title} album cover" width="180" height="180" loading="lazy">
      <figcaption>© respective label — fair use</figcaption>
    </figure>'''
    else:
        cover_html = ''

    github_url = f"{GITHUB_BASE}/{album['content_file']}"

    body = f'''<div class="album-page">
  <header class="album-header">
    <div class="album-header__content">
      <a class="album-header__back" href="/">← All Albums</a>
      <div class="album-header__label">{label} · {year}</div>
      <h1 class="album-header__title">{title}</h1>
      <p class="album-header__artist">{artist}</p>
      <div class="album-header__facts">
        <span>Recorded:</span> {album['recorded']} &nbsp;
        <span>Original cat#:</span> {album['original_cat']}
      </div>
    </div>
{cover_html}
  </header>

  <aside class="album-toc">
    <p class="album-toc__heading">On this page</p>
    <ul class="album-toc__list" id="toc-list"></ul>
  </aside>

  <article class="album-content" id="album-content">
    {content_html}
    <div class="contribute-banner">
      <p><strong>Know something we don't?</strong> Spotted an error or have a pressing to add?</p>
      <a class="btn" href="{github_url}" target="_blank" rel="noopener">Edit this page on GitHub</a>
    </div>
  </article>
</div>'''

    html = html_shell(title, album['description'], body)
    out  = os.path.join(OUTPUT_DIR, "albums", f"{slug}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        f.write(html)
    print(f"  ✓ albums/{slug}.html")

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    with open(ALBUMS_FILE) as f:
        albums = json.load(f)

    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target:
        # Build one album + regenerate index
        match = [a for a in albums if a['slug'] == target]
        if not match:
            print(f"Album '{target}' not found in albums.json")
            sys.exit(1)
        print(f"Building {target}...")
        build_album(match[0])
        print("Regenerating index...")
        build_index(albums)
    else:
        # Build everything
        print("Building all pages...")
        build_index(albums)
        for album in albums:
            build_album(album)

    print("\nDone. Upload changed files to GitHub.")

if __name__ == "__main__":
    main()
