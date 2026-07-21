#!/usr/bin/env python3
import json, os, re, sys, urllib.request, urllib.error, urllib.parse
from datetime import datetime

try:
    import markdown
except ImportError:
    os.system("pip3 install markdown --break-system-packages -q")
    import markdown

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR   = os.path.join(BASE_DIR, "_content")
OUTPUT_DIR    = BASE_DIR
ALBUMS_FILE   = os.path.join(BASE_DIR, "albums.json")
MARKET_FILE   = os.path.join(BASE_DIR, "market_data.json")
GITHUB_BASE   = "https://github.com/Jazz-vinyl-club/jazzvinylguide/edit/main/_content"
GITHUB_API    = "https://api.github.com/repos/Jazz-vinyl-club/jazzvinylguide/commits"

# Low-to-high, matches fetch_market_data.py's CONDITIONS list exactly --
# both must stay in sync since this reads that script's output. Kept as the
# full canonical list even though only the top 3 are rendered now (G/VG
# dropped from the ladder per request -- the data stays in market_data.json
# either way, just unrendered).
MARKET_CONDITIONS = [
    "Good (G)",
    "Very Good (VG)",
    "Very Good Plus (VG+)",
    "Near Mint (NM or M-)",
    "Mint (M)",
]
DISPLAYED_MARKET_CONDITIONS = [
    "Very Good Plus (VG+)",
    "Near Mint (NM or M-)",
    "Mint (M)",
]

CURRENCY_SYMBOLS = {"USD": "$", "AUD": "A$", "GBP": "£", "EUR": "€"}

TIER_TABLE_RE = re.compile(
    r'(<div class="table-wrap"><table>\s*<thead>.*?<th>Tier</th>.*?</table></div>)', re.S
)
ROW_RE = re.compile(r'<tr>.*?</tr>', re.S)
CELL_RE = re.compile(r'<td.*?</td>', re.S)
CELL_INNER_RE = re.compile(r'<td[^>]*>(.*)</td>', re.S)
DISCOGS_HREF_RE = re.compile(r'href="([^"]*discogs\.com/release/\d+[^"]*)"')
RELEASE_ID_IN_HREF_RE = re.compile(r'discogs\.com/release/(\d+)')

MARKET_SORT_SCRIPT = """<script>
(function(){
  function numOrInf(v){ var n = parseFloat(v); return isNaN(n) ? Infinity : n; }
  function dataRows(table){
    return Array.prototype.filter.call(table.querySelectorAll('tr'), function(r){ return r.querySelector('td'); });
  }
  function reorder(rows){
    if(!rows.length) return;
    var parent = rows[0].parentNode;
    rows.forEach(function(r){ parent.appendChild(r); });
  }
  // F tier is 'avoid, do not buy' by this site's own tier criteria -- it
  // stays pinned last under every sort, in either direction, rather than
  // ever floating to the top just because it happens to be cheap or old.
  function fPinnedCompare(a, b, valueCompareFn){
    var aF = a.getAttribute('data-tier') === 'F';
    var bF = b.getAttribute('data-tier') === 'F';
    if(aF && bF) return 0;
    if(aF) return 1;
    if(bF) return -1;
    return valueCompareFn(a, b);
  }

  document.querySelectorAll('.tier-table').forEach(function(table){
    var theadThs = table.querySelectorAll('thead th');
    var tierTh = theadThs[0];
    var yearTh = theadThs[3];
    var marketTh = theadThs[theadThs.length - 1];
    if(!tierTh || !yearTh || !marketTh) return;

    [tierTh, yearTh, marketTh].forEach(function(th){
      th.classList.add('market-sort-th');
    });

    var marketAsc = true, yearAsc = true;

    function resetLabels(except){
      if(except !== marketTh) marketTh.textContent = 'Market \\u21c5';
      if(except !== yearTh) yearTh.textContent = 'Year \\u21c5';
    }

    marketTh.addEventListener('click', function(){
      var rows = dataRows(table);
      var asc = marketAsc;
      rows.sort(function(a, b){
        return fPinnedCompare(a, b, function(a, b){
          var av = numOrInf(a.getAttribute('data-vgplus-price'));
          var bv = numOrInf(b.getAttribute('data-vgplus-price'));
          return asc ? av - bv : bv - av;
        });
      });
      reorder(rows);
      resetLabels(marketTh);
      marketTh.textContent = 'Market ' + (asc ? '\\u25be' : '\\u25b4');
      marketAsc = !marketAsc;
    });

    yearTh.addEventListener('click', function(){
      var rows = dataRows(table);
      var asc = yearAsc;
      rows.sort(function(a, b){
        return fPinnedCompare(a, b, function(a, b){
          var av = numOrInf(a.getAttribute('data-year'));
          var bv = numOrInf(b.getAttribute('data-year'));
          return asc ? av - bv : bv - av;
        });
      });
      reorder(rows);
      resetLabels(yearTh);
      yearTh.textContent = 'Year ' + (asc ? '\\u25be' : '\\u25b4');
      yearAsc = !yearAsc;
    });

    tierTh.addEventListener('click', function(){
      var rows = dataRows(table);
      rows.sort(function(a, b){
        return parseInt(a.getAttribute('data-default-index'), 10) - parseInt(b.getAttribute('data-default-index'), 10);
      });
      reorder(rows);
      resetLabels(null);
      marketAsc = true;
      yearAsc = true;
    });
  });
})();
</script>"""


def load_market_data():
    if not os.path.exists(MARKET_FILE):
        return {}
    with open(MARKET_FILE) as f:
        return json.load(f)


CONDITION_INITIALS = {
    "Good (G)": "G",
    "Very Good (VG)": "VG",
    "Very Good Plus (VG+)": "VG+",
    "Near Mint (NM or M-)": "NM",
    "Mint (M)": "M",
}


def render_market_cell(release_id, market_data):
    """Renders one tier-table row's market cell: a real summary line (total
    copies for sale + lowest price, both release-wide -- Discogs doesn't
    expose these broken out by condition, confirmed against the documented
    API parameters) plus a line-and-dots ladder for suggested_price at VG+,
    NM, and Mint (Good/VG dropped from display -- still in market_data.json,
    just cluttered the ladder at this width and matter less for guides
    whose own tier criteria treat sub-VG as "avoid unless price is
    exceptional"). Falls back to a quiet placeholder if this release hasn't
    been fetched yet."""
    entry = market_data.get(release_id)
    if not entry:
        return '<span class="market-pending">market data pending</span>'

    symbol = CURRENCY_SYMBOLS.get(entry.get("currency", "USD"), "$")
    for_sale = entry.get("for_sale") or 0
    lowest_price = entry.get("lowest_price")
    suggested = entry.get("suggested_prices", {})

    if for_sale and lowest_price:
        summary_html = (
            f'<a href="https://www.discogs.com/sell/release/{release_id}" class="market-summary-link">'
            f'{for_sale} for sale · from {symbol}{lowest_price:,.0f}</a>'
        )
    else:
        summary_html = '<span class="market-summary-none">none currently listed</span>'

    suggested_values = [suggested.get(c) for c in DISPLAYED_MARKET_CONDITIONS if suggested.get(c)]
    max_price = max(suggested_values) if suggested_values else None

    dots_html = ""
    for cond in DISPLAYED_MARKET_CONDITIONS:
        price = suggested.get(cond)
        if price and max_price:
            size = 6 + round(4 * (price / max_price))
            price_label = f"{symbol}{price:,.0f}"
        else:
            size = 6
            price_label = "—"

        dots_html += (
            f'<div class="market-dot-col">'
            f'<span class="market-price">{price_label}</span>'
            f'<span class="market-dot" style="width:{size}px;height:{size}px;"></span>'
            f'<span class="market-cond-label">{CONDITION_INITIALS[cond]}</span>'
            f'</div>'
        )

    return (
        f'<div class="market-cell-inner">'
        f'<div class="market-summary">{summary_html}</div>'
        f'<div class="market-ladder">{dots_html}</div>'
        f'</div>'
    )


TIER_TEXT_RE = re.compile(r'<td><strong>([SABCDF])</strong></td>')
YEAR_TEXT_RE = re.compile(r'<td>[^<]*?(\d{4})[^<]*</td>')


def inject_market_column(content_html, market_data):
    """Finds the tier table (identified by its 'Tier' header, so this never
    touches other tables like a Buyer's Guide comparison) and restructures
    it: the standalone Discogs column is dropped and its link folded onto
    the Cat# cell instead, and a sortable Market column (real summary +
    suggested-price ladder, sourced from market_data.json) takes its place
    as the last column -- same position Discogs held, so no reordering of
    the other columns is needed. Also widens the table beyond the normal
    prose column width. Leaves content_html completely untouched if the
    tier table isn't found."""
    match = TIER_TABLE_RE.search(content_html)
    if not match:
        return content_html

    table_html = match.group(1)
    table_html = table_html.replace("<table>", '<table class="tier-table">', 1)
    table_html = table_html.replace("<th>Tier</th>", '<th>Tier \u21c5</th>', 1)
    table_html = table_html.replace("<th>Year</th>", '<th>Year \u21c5</th>', 1)
    table_html = table_html.replace("<th>Discogs</th>", '<th>Market \u21c5</th>', 1)

    row_index = [0]

    def process_row(row_match):
        row_html = row_match.group(0)
        cells = CELL_RE.findall(row_html)
        if len(cells) < 8:
            return row_html  # header row or unrecognized shape -- leave untouched

        tier_match = TIER_TEXT_RE.match(cells[0])
        tier = tier_match.group(1) if tier_match else ""

        year_match = YEAR_TEXT_RE.match(cells[3])
        year = year_match.group(1) if year_match else ""

        discogs_cell = cells[7]
        href_match = DISCOGS_HREF_RE.search(discogs_cell)

        vgplus_price = None
        if href_match:
            href = href_match.group(1)
            release_id_match = RELEASE_ID_IN_HREF_RE.search(href)
            release_id = release_id_match.group(1) if release_id_match else None

            catnum_inner_match = CELL_INNER_RE.match(cells[2])
            catnum_inner = catnum_inner_match.group(1) if catnum_inner_match else ""
            cells[2] = f'<td><a href="{href}" class="market-catnum-link">{catnum_inner}</a></td>'

            if release_id:
                market_cell_html = render_market_cell(release_id, market_data)
                entry = market_data.get(release_id) or {}
                vgplus_price = entry.get("suggested_prices", {}).get("Very Good Plus (VG+)")
            else:
                market_cell_html = '<span class="market-pending">market data pending</span>'
        else:
            market_cell_html = '<span class="market-none">\u2013</span>'

        cells[7] = f'<td class="market-cell">{market_cell_html}</td>'

        sort_value = vgplus_price if vgplus_price is not None else ""
        idx = row_index[0]
        row_index[0] += 1

        attrs = f'data-vgplus-price="{sort_value}" data-tier="{tier}" data-year="{year}" data-default-index="{idx}"'
        return f"<tr {attrs}>\n" + "\n".join(cells) + "\n</tr>"

    table_html = ROW_RE.sub(process_row, table_html)
    table_html = table_html.replace(
        '<div class="table-wrap">', '<div class="table-wrap tier-table-wrap">', 1
    )
    return content_html[: match.start()] + table_html + content_html[match.end() :] + MARKET_SORT_SCRIPT


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
        title_esc = a['title']
        itunes_query = urllib.parse.quote(f"{a['artist']} {a['title']}")
        if mbid:
            thumb = f'<img src="https://coverartarchive.org/release-group/{mbid}/front-250" alt="{title_esc}" class="album-card__cover" loading="lazy" data-itunes-fallback="{itunes_query}" onerror="window.tryItunesCoverFallback(this)">'
        else:
            thumb = f'<img alt="{title_esc}" class="album-card__cover" loading="lazy" data-itunes-fallback="{itunes_query}">'
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
    content_html = inject_market_column(content_html, load_market_data())

    mbid = album.get('mbid', '')
    itunes_query = urllib.parse.quote(f"{artist} {title}")
    if mbid:
        # Try Cover Art Archive via mbid first; if that specific release-group
        # has no art registered (a real, fairly common gap), fall back to an
        # iTunes Search API lookup by artist+title at runtime in the visitor's
        # browser. iTunes has near-universal commercial-release coverage and
        # needs no mbid or API key, so this self-heals future albums too
        # without anyone needing to manually source and commit an image file.
        # One standard for every album -- no separate pre-committed-file path.
        cover_html = f'''    <figure class="album-header__cover">
      <img src="https://coverartarchive.org/release-group/{mbid}/front-500" alt="{title} album cover" width="160" height="160" loading="lazy" data-itunes-fallback="{itunes_query}" onerror="window.tryItunesCoverFallback(this)">
    </figure>'''
    else:
        # No mbid at all -- go straight to the iTunes fallback. main.js scans
        # for cover images with no src on page load and triggers the lookup
        # directly, since a missing src doesn't reliably fire onerror in
        # every browser.
        cover_html = f'''    <figure class="album-header__cover">
      <img alt="{title} album cover" width="160" height="160" loading="lazy" data-itunes-fallback="{itunes_query}">
    </figure>'''

    # Public album pages no longer surface "Last updated / update history" -
    # that's for internal tracking only. Changelog pages are still generated
    # (build_changelog below) and reachable by direct URL if needed.
    updated_html = ''

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


def fetch_full_commit_history(filename):
    """Fetch full commit history (sha, date, message) for a content file from GitHub API.
    Returns a list of dicts, most recent first. Empty list on any failure."""
    try:
        tok = os.environ.get("GITHUB_TOKEN", "")
        api_url = GITHUB_API + "?path=_content/" + filename + "&per_page=100"
        hdr = {"Accept": "application/vnd.github.v3+json"}
        if tok:
            hdr["Authorization"] = "token " + tok
        req = urllib.request.Request(api_url, headers=hdr)
        with urllib.request.urlopen(req, timeout=10) as r:
            commits = json.loads(r.read())
        out = []
        for c in commits:
            date_str = c["commit"]["committer"]["date"]
            dt = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            out.append({
                "sha": c["sha"][:7],
                "date": dt.strftime("%B %d, %Y"),
                "time": dt.strftime("%H:%M UTC"),
                "message": c["commit"]["message"],
            })
        return out
    except Exception:
        return []


def build_changelog(album):
    """Build the hidden per-album changelog page at /albums/<slug>-changelog.html.
    Not linked from primary nav; reachable from status.html and a subtle link
    on the album page itself."""
    slug, title = album["slug"], album["title"]
    commits = fetch_full_commit_history(album["content_file"])
    if not commits:
        rows = "<tr><td colspan=\"3\">No commit history available.</td></tr>"
    else:
        rows = ""
        for i, c in enumerate(commits):
            version_label = f"v{len(commits) - i}"
            # Preserve line breaks in multi-paragraph commit messages as separate lines.
            msg_html = "<br>".join(
                m.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                for m in c["message"].split("\n") if m.strip()
            )
            rows += (
                "<tr><td class=\"changelog-date\">" + c["date"] + "<br>"
                "<span class=\"changelog-time\">" + c["time"] + "</span></td>"
                "<td class=\"changelog-version\">" + version_label
                + " <span class=\"changelog-sha\">(" + c["sha"] + ")</span></td>"
                "<td class=\"changelog-notes\">" + msg_html + "</td></tr>\n"
            )
    body = (
        "<div class=\"status-page\">"
        "<a class=\"album-header__back\" href=\"/albums/" + slug + ".html\">&larr; Back to guide</a>"
        "<h1 class=\"status-title\">" + title + " &mdash; Update Log</h1>"
        "<p class=\"status-subtitle\">Every recorded change to this guide's content, most recent first. "
        "Auto-generated from git history on every build.</p>"
        "<table class=\"status-table changelog-table\"><colgroup><col><col><col></colgroup>"
        "<thead><tr><th>Date &amp; time</th><th>Version</th><th>Notes</th></tr></thead>"
        "<tbody>" + rows + "</tbody></table></div>"
    )
    out = os.path.join(OUTPUT_DIR, "albums", f"{slug}-changelog.html")
    with open(out, "w") as f:
        f.write(html_shell(title + " Update Log", "Update history for the " + title + " vinyl pressing guide.", body))
    print(f"  ✓ albums/{slug}-changelog.html")


def fetch_commit_history(filename):
    """Fetch full commit history for a content file from GitHub API."""
    try:
        import os as _os
        tok = _os.environ.get("GITHUB_TOKEN", "")
        api_url = GITHUB_API + "?path=_content/" + filename + "&per_page=100"
        hdr = {"Authorization": "token " + tok, "Accept": "application/vnd.github.v3+json"}
        req = urllib.request.Request(api_url, headers=hdr)
        with urllib.request.urlopen(req, timeout=10) as r:
            commits = json.loads(r.read())
        if not commits:
            return None, None, []
        first = commits[-1]["commit"]["committer"]["date"][:10]
        last  = commits[0]["commit"]["committer"]["date"][:10]
        messages = [c["commit"]["message"].lower() for c in commits]
        return first, last, messages
    except Exception:
        return None, None, []

def classify_status(first, last, messages):
    """Dynamically classify a guide's status from its commit history."""
    updated = first != last if (first and last) else False
    all_msgs = " ".join(messages)
    is_rewrite = any(w in all_msgs for w in ["rewrite", "full content upgrade", "full upgrade"])
    is_auto_fc = any(w in all_msgs for w in ["automated fact-check", "gemini", "pipeline"])
    is_manual_fc = any(w in all_msgs for w in ["fact-check", "fact check", "fix ", "correct", "fixes"])
    return updated, is_rewrite, is_manual_fc, is_auto_fc


def build_status(albums):
    """Build the hidden status/tracking page at /status.html."""
    print("  Building status page...")
    rows = ""
    for a in albums:
        first, last, messages = fetch_commit_history(a["content_file"])
        updated, is_rewrite, is_manual_fc, is_auto_fc = classify_status(first, last, messages)
        d = last or ""
        if is_rewrite:
            dc = "<td class=\"status-yes\">Full rewrite<br><span class=\"status-date\">" + d + "</span></td>"
        elif updated:
            dc = "<td class=\"status-yes\">Updated<br><span class=\"status-date\">" + d + "</span></td>"
        else:
            dc = "<td class=\"status-no\">&#8212;</td>"
        if is_auto_fc and is_manual_fc:
            fc = "<td class=\"status-yes\">Manual + Automated<br><span class=\"status-date\">" + d + "</span></td>"
        elif is_manual_fc:
            fc = "<td class=\"status-yes\">Manual<br><span class=\"status-date\">" + d + "</span></td>"
        else:
            fc = "<td class=\"status-no\">&#8212;</td>"
        link = "<a href=\"/albums/" + a["slug"] + ".html\">" + a["title"] + "</a>"
        history_link = " <a class=\"changelog-link\" href=\"/albums/" + a["slug"] + "-changelog.html\">(history)</a>"
        rows += ("<tr><td>" + link + history_link + "</td><td>" + a["artist"] + "</td>"
                 + "<td class=\"status-date\">" + (first or "&#8212;") + "</td>"
                 + dc + fc + "</tr>\n")
    from datetime import datetime, timezone
    gen = datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC")
    body = (
        "<div class=\"status-page\">"
        "<h1 class=\"status-title\">Guide Status &amp; Update Log</h1>"
        "<p class=\"status-subtitle\">Auto-generated on every build. Last built: " + gen + ".</p>"
        "<table class=\"status-table\"><colgroup><col><col><col><col><col></colgroup>"
        "<thead><tr><th>Album</th><th>Artist</th><th>First Drafted</th>"
        "<th>Detail Upgrade</th><th>Fact-Check</th></tr></thead>"
        "<tbody>" + rows + "</tbody></table></div>"
    )
    out = os.path.join(OUTPUT_DIR, "status.html")
    with open(out, "w") as f:
        f.write(html_shell("Guide Status", "Internal status tracking for jazzvinylguide.com.", body))
    print("  \u2713 status.html")


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
        build_changelog(match[0])
        build_index(albums)
    else:
        print("Building all pages...")
        build_index(albums)
        build_status(albums)
        for a in albums:
            build_album(a)
            build_changelog(a)
    print("\nDone.")

if __name__ == "__main__":
    main()

# status page support added
