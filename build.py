#!/usr/bin/env python3
import json, os, re, sys

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

def md_to_html(md_text):
    lines = md_text.split('\n')
    if lines and lines[0].startswith('# '):
        lines = lines[1:]
    if lines and re.match(r'^\*[^*]+\*\s*$', lines[0].strip()):
        lines = lines[1:]
    text = '\n'.join(lines)
    md = markdown.Markdown(extensions=['tables', 'fenced_code'])
    return md.convert(text)

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
    out = os.path.join(OUTPUT_DIR, "index.html")
    with open(out, 'w') as f:
        f.write(html_shell("Jazz Vinyl Guide", "Collector-grade vinyl pressing guides for essential jazz albums.", body))
    print(f"  ✓ index.html")

def build_album(album):
    slug   = album['slug']
    title  = album['title']
    artist = album['artist']
    label  = album['label']
    year   = album['year']

    content_path = os.path.join(CONTENT_DIR, album['content_file'])
    if not os.path.exists(content_path):
        print(f"  ⚠ Missing: {content_path}")
        return
    with open(content_path, 'r') as f:
        md_text = f.read()
    content_html = md_to_html(md_text)

    cover_path = os.path.join(BASE_DIR, "covers", f"{slug}.jpg")
    if os.path.exists(cover_path):
        cover_html = f'''    <figure class="album-header__cover">
      <img src="/covers/{slug}.jpg" alt="{title} album cover" width="160" height="160" loading="lazy">
      <figcaption>© respective label — fair use</figcaption>
    </figure>'''
    else:
        cover_html = ''
        print(f"  ⚠ No cover for {slug}")

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
  <div class="album-summary" id="album-summary"></div>
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
            print(f"Not found: {target}")
            sys.exit(1)
        build_album(match[0])
        build_index(albums)
    else:
        print("Building all pages...")
        build_index(albums)
        for album in albums:
            build_album(album)
    print("\nDone.")

if __name__ == "__main__":
    main()
