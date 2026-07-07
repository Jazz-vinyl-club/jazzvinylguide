#!/usr/bin/env python3
import json, os, re, sys, urllib.request, urllib.error
from datetime import datetime

try:
    import markdown
except ImportError:
    os.system("pip3 install markdown --break-system-packages -q")
    import markdown

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, "_content")
OUTPUT_DIR  = BASE_DIR
ALBUMS_FILE = os.path.join(BASE_DIR, "albums.json")
GITHUB_BASE = "https://github.com/Jazz-vinyl-club/jazzvinylguide/edit/main/_content"
GITHUB_API  = "https://api.github.com/repos/Jazz-vinyl-club/jazzvinylguide/commits"

def get_last_updated(content_file):
    """Fetch last commit date for a file from GitHub API."""
    try:
        url = f"{GITHUB_API}?path=_content/{content_file}&per_page=1"
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            commits = json.loads(r.read())
            if commits:
                date_str = commits[0]['commit']['committer']['date']
                dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
                return dt.strftime("%B %Y")
    except Exception:
        pass
    return None

def site_header():
    return '''<header class="site-header">
  <div class="site-header__inner">
    <a class="site-logo" href="/"><img src="/logo.png" alt="Jazz Vinyl Guide" height="40"></a>
    <nav class="site-nav">
      <a href="/">Albums</a>
      <a href="/contribute.html">Contribute</a>
    </nav>
  </div>
</header>'''

def site_footer():
    return '''<footer class="site-footer">
  <p><a href="https://jazzvinylguide.com">jazzvinylguide.com</a> — Collector-grade pressing guides. <a href="/contribute.html">Contribute</a>.</p>
</footer>'''

def html_shell(title, description, body):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — Jazz Vinyl Guide</title>
  <meta name="description" content="{description}">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
{site_header()}
<main>{body}</main>
{site_footer()}
<script src="/main.js"></script>
</body>
</html>'''

def _render(text):
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    html = md.convert(text)
    html = html.replace('<table>', '<div class="table-wrap"><table>').replace('</table>', '</table></div>')
    return html

def strip_preamble(lines):
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    if lines and re.match(r'^\*[^*]+\*\s*$', lines[0].strip()):
        lines = lines[1:]
    return lines

def extract_summary(md_text):
    lines = strip_preamble(md_text.split('\n'))
    summary_lines, rest_lines = [], []
    in_summary = found = False
    for line in lines:
        if line.strip() == '## Summary':
            in_summary = found = True
            continue
        if in_summary:
            if line.startswith('## '):
                in_summary = False
                rest_lines.append(line)
            else:
                summary_lines.append(line)
        else:
            rest_lines.append(line)
    if not found:
        return '', _render('\n'.join(lines))
    return _render('\n'.join(summary_lines).strip()), _render('\n'.join(rest_lines))

def build_index(albums):
    rows = ""
    for a in albums:
        mbid = a.get('mbid', '')
        title_lower  = a['title'].lower().replace('"', '&quot;')
        artist_lower = a['artist'].lower().replace('"', '&quot;')
        label_lower  = a['label'].lower().replace('"', '&quot;')
        year_val     = str(a['year'])
        if mbid:
            title_esc = a['title']
            thumb = f'<img src="https://coverartarchive.org/release-group/{mbid}/front-250" alt="{title_esc}" class="album-card__cover" loading="lazy" onerror="this.style.display:none">'
        else:
            cp = os.path.join(BASE_DIR, "covers", f"{a['slug']}.jpg")
            slug_val = a['slug']
            title_val = a['title']
            thumb = f'<img src="/covers/{slug_val}.jpg" alt="{title_val}" class="album-card__cover">' if os.path.exists(cp) else ''
        rows += f'''    <a class="album-card" href="/albums/{a['slug']}.html" data-title="{title_lower}" data-artist="{artist_lower}" data-label="{label_lower}" data-year="{year_val}">
      {thumb}
      <h2 class="album-card__title">{a['title']}</h2>
      <p class="album-card__artist">{a['artist']}</p>
      <p class="album-card__meta">{a['label']} · {a['year']}</p>
      <span class="album-card__arrow">Read full guide →</span>
    </a>\n'''
    body = f'''<section class="hero">
  <h1 class="hero__title">Collector-grade guides for essential jazz albums</h1>
</section>
<section class="albums-section">
  <div class="albums-controls">
    <input class="albums-search" id="albumSearch" type="search" placeholder="Search albums, artists, labels…" autocomplete="off" spellcheck="false">
    <div class="albums-sort">
      <span class="albums-sort__label">Sort by</span>
      <button class="albums-sort__btn active" data-sort="default">Default</button>
      <button class="albums-sort__btn" data-sort="title">Title</button>
      <button class="albums-sort__btn" data-sort="artist">Artist</button>
      <button class="albums-sort__btn" data-sort="year">Year</button>
    </div>
  </div>
  <div class="album-grid" id="albumGrid">
{rows}  </div>
  <p class="albums-no-results" id="albumsNoResults" style="display:none">No albums match your search.</p>
</section>'''
    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, 'w') as f:
        f.write(html_shell("Jazz Vinyl Guide", "Collector-grade vinyl pressing guides for essential jazz albums.", body))
    print("  ✓ index.html")

def build_album(album):
    slug, title, artist, label, year = album['slug'], album['title'], album['artist'], album['label'], album['year']
    cp = os.path.join(CONTENT_DIR, album['content_file'])
    if not os.path.exists(cp):
        print(f"  ⚠ Missing: {cp}"); return
    with open(cp, 'r') as f:
        md_text = f.read()

    summary_html, content_html = extract_summary(md_text)

    mbid = album.get('mbid', '')
    if mbid:
        cover_html = f'''    <figure class="album-header__cover">
      <img src="https://coverartarchive.org/release-group/{mbid}/front-500" alt="{title} album cover" width="160" height="160" loading="lazy" onerror="this.style.display='none'">
    </figure>'''
    else:
        cover_path = os.path.join(BASE_DIR, "covers", f"{slug}.jpg")
        if os.path.exists(cover_path):
            cover_html = f'''    <figure class="album-header__cover">
      <img src="/covers/{slug}.jpg" alt="{title} album cover" width="160" height="160" loading="lazy">
    </figure>'''
        else:
            cover_html = ''

    last_updated = get_last_updated(album['content_file'])
    updated_html = f'<p class="last-updated">Last updated: {last_updated}</p>' if last_updated else ''

    github_url = f"{GITHUB_BASE}/{album['content_file']}"
    body = f'''<div class="album-page">
  <a class="album-header__back" href="/">← All Albums</a>
  <header class="album-header">
    <div class="album-header__content">
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
  <div class="album-summary" id="album-summary">{summary_html}</div>
  <aside class="album-toc">
    <a class="album-toc__heading album-toc__top" href="#">↑ Top</a>
    <ul class="album-toc__list" id="toc-list"></ul>
  </aside>
  <article class="album-content" id="album-content">
    {content_html}
    <div class="contribute-banner">
      <p><strong>Know something we don't?</strong> Spotted an error or have a pressing to add?</p>
      <a class="btn" href="{github_url}" target="_blank" rel="noopener">Edit this page on GitHub</a>
      {updated_html}
    </div>
  </article>
</div>'''

    out = os.path.join(OUTPUT_DIR, "albums", f"{slug}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w') as f:
        f.write(html_shell(title, album['description'], body))
    print(f"  ✓ albums/{slug}.html")

def main():
    with open(ALBUMS_FILE) as f:
        albums = json.load(f)
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target:
        match = [a for a in albums if a['slug'] == target]
        if not match:
            print(f"Not found: {target}"); sys.exit(1)
        print(f"Building {target}...")
        build_album(match[0])
        build_index(albums)
    else:
        print("Building all pages...")
        build_index(albums)
        for a in albums:
            build_album(a)
    print("\nDone.")

if __name__ == "__main__":
    main()

# status page support added
