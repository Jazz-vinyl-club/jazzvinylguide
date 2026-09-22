"""
style_checks.py — prose, structure and depth checks for full_audit.py.

Rules come from STYLE.md at the repo root. Errors fail the audit; warnings
flag text for the rewrite pass. The prose heuristics are deliberately
simple: they catch known patterns, not every instance of bad writing, so a
clean result here does not replace reading the guide.
"""

import re

REQUIRED_SECTIONS = [
    "Summary",
    "Recording history and tape provenance",
    "Buyer's guide by budget",
    "Pressing tier summary",
    "References",
]

SENTENCE_WARN = 25
SENTENCE_FAIL = 35
PARA_MAX_SENTENCES = 4
PARA_MAX_WORDS = 90
SUMMARY_PARA_MIN_WORDS = 50
WORDS_PER_PRESSING_MIN = 150

FIRST_PERSON_RE = re.compile(r"\b(I|I'm|I've|I'd|my|me|we|we've|our|us)\b")
SITE_REF_RE = re.compile(
    r"\b(this site|on the site|other guides?|elsewhere on|guides on|most of the guides|"
    r"this guide|these guides)\b", re.I)
SECOND_PERSON_RE = re.compile(r"\b(you|your|you're|you'll|yourself)\b", re.I)
REFERENCE_WORD_RE = re.compile(
    r"\b(review|reviewer|reviewers|video|forum|thread|interview|article|podcast|"
    r"YouTube channel|blog|write-up|liner notes)\b", re.I)
CONSENSUS_RE = re.compile(
    r"\b(widely (rated|regarded|considered|praised|cited)|generally (considered|regarded|agreed)|"
    r"most (agree|listeners|collectors|reviewers)|universally|often cited|commonly (cited|regarded))\b", re.I)
POSITIONAL_RE = re.compile(r"\b(see )?(below|above)\b(?! average)", re.I)
FLOURISH_PHRASES = [
    "by circumstance rather than design", "both are probably true", "worth knowing",
    "worth being precise", "worth noting", "worth making", "surfaces a real correction",
    "almost as a response", "a small piece of trivia", "what makes", "more remarkable",
    "fundamentally different proposition", "in other words", "tells a more specific story",
    "the clearest", "it's worth", "it is worth", "make no mistake", "the real story",
    "not just", "rather than fight", "a genuine", "genuinely",
]
PROCESS_RE = re.compile(
    r"\b(independently confirmed|a real correction|correction worth|we confirmed|"
    r"confirmed directly|this guide previously|earlier version)\b", re.I)
SCOPE_WORDS_RE = re.compile(
    r"\b(Billboard|Hall of Fame|Grammy|stars|chart(ed|s)?|named it|favou?rite albums?|"
    r"Analogue Productions|Classic Records|Music Matters|Tone Poet|Mobile Fidelity|MoFi|"
    r"Speakers Corner|Quality Record Pressings|QRP|Acoustic Sounds|Craft Recordings|OJC|"
    r"Original Jazz Classics|Impex|Supersense|Pure Pleasure|Electric Recording)\b")

ABBREVS = ["c.", "e.g.", "i.e.", "No.", "Vol.", "vol.", "Mr.", "Mrs.", "St.", "Dr.",
           "Jr.", "Sr.", "vs.", "U.S.", "U.K.", "T.M.", "approx.", "Inc.", "Ltd.", "Co."]


def split_sections(content):
    parts = re.split(r"^## ", content, flags=re.M)
    out = []
    for p in parts[1:]:
        head, _, body = p.partition("\n")
        out.append((head.strip(), body))
    return out


def strip_md(text):
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # links -> text
    text = re.sub(r"https?://\S+", "", text)
    text = text.replace("**", "")
    return text


def strip_quoted(text):
    """Remove quoted titles/quotes and italics so song titles like
    "I'm a Fool to Want You" don't trip person/flourish checks."""
    text = re.sub(r"\"[^\"\n]*\"", '""', text)
    text = re.sub(r"\u201c[^\u201d\n]*\u201d", '""', text)
    text = re.sub(r"(?<![*\w])\*(?!\*)[^*\n]+\*(?!\*)", "TITLE", text)
    return text


def sentences(text):
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) > 1 and all(l.lstrip().startswith(("- ", "* ")) for l in lines):
        out = []
        for l in lines:
            out.extend(_sentences(l.lstrip()[2:]))
        return out
    return _sentences(text)


def _sentences(text):
    t = strip_md(text)
    for a in ABBREVS:
        t = t.replace(a, a.replace(".", "\u2024"))
    t = re.sub(r"(\d)\.(\d)", "\\1\u2024\\2", t)
    t = re.sub(r"\b([A-Z])\.(?=\s)", "\\1\u2024", t)   # initials: "J. J. Johnson"
    parts = re.split(r"(?<=[.!?])[\"\u201d)]?\s+(?=[\"\u201c(*]?[A-Z0-9])", t)
    return [p.replace("\u2024", ".").strip() for p in parts if p.strip()]


def wc(s):
    return len(re.findall(r"[\w'’⅓×$#-]+", s))


def prose_blocks(body):
    """Paragraphs of prose: skip tables, headings, blank lines."""
    blocks = [b for b in body.split("\n\n") if b.strip()]
    out = []
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if not lines or all(l.lstrip().startswith("|") for l in lines):
            continue
        if lines[0].startswith("#"):
            continue
        out.append(b.strip())
    return out


def table_note_cells(body):
    cells = []
    for l in body.split("\n"):
        if l.startswith("| **"):
            cols = [c.strip() for c in l.split("|")]
            if len(cols) > 7:
                cells.append(cols[7])
    return cells


def short(s, n=90):
    s = " ".join(s.split())
    return s if len(s) <= n else s[:n] + "..."


def check_structure(secs, r):
    heads = [h for h, _ in secs]
    for req in REQUIRED_SECTIONS:
        if req not in heads:
            r.error(f"required section missing: '## {req}'")
    order = [h for h in heads if h in REQUIRED_SECTIONS]
    expected = [h for h in REQUIRED_SECTIONS if h in heads]
    if order != expected:
        r.error(f"required sections out of order: {order}")


def check_summary(body, r):
    lines = body.split("\n")
    for l in lines:
        if re.match(r"^\*\*Best ", l.strip()):
            r.error(f"'Best ...' line must be a bullet ('- **Best ...'): {short(l, 60)}")
    prose = re.split(r"^\s*[-*]?\s*\*\*Best ", body, maxsplit=1, flags=re.M)[0]
    paras = [p for p in prose.split("\n\n") if p.strip()]
    if len(paras) != 2:
        r.error(f"Summary must have exactly 2 paragraphs before the 'Best' bullets (has {len(paras)})")
    for i, p in enumerate(paras, 1):
        if wc(strip_md(p)) < SUMMARY_PARA_MIN_WORDS:
            r.warn(f"Summary paragraph {i} is under {SUMMARY_PARA_MIN_WORDS} words ({wc(strip_md(p))})")


def check_buyers_guide(body, r):
    for l in body.split("\n"):
        if re.match(r"^\s*[-*]?\s*\*\*\$+[^*]*\(", l):
            r.error(f"buyer's guide band has a tier descriptor (keep $ only): {short(l, 60)}")


def check_recording_scope(body, r):
    hits = sorted(set(m.group(0) for m in SCOPE_WORDS_RE.finditer(strip_quoted(body))))
    if hits:
        r.warn(f"Recording history mentions reception/awards or reissue labels "
               f"(move pressing detail to pressing sections, cut reception): {hits}")


def check_prose(secs, r):
    for head, body in secs:
        if head == "References":
            continue
        in_buyers = head.startswith("Buyer's guide")
        units = [(b, "para") for b in prose_blocks(body)]
        if head == "Pressing tier summary":
            units = [(c, "cell") for c in table_note_cells(body)]
        for block, kind in units:
            raw_q = strip_quoted(block)
            clean = strip_quoted(strip_md(block))
            where = f"[{head}]"

            if FIRST_PERSON_RE.search(clean):
                r.error(f"{where} first person: {short(block)}")
            if SITE_REF_RE.search(clean):
                r.error(f"{where} reference to the site or other guides: {short(block)}")
            if PROCESS_RE.search(clean):
                r.error(f"{where} narrates the guide's own editing/verification: {short(block)}")
            if re.search(r"\[Discogs\]\(", block) and kind == "para":
                r.error(f"{where} prose link text 'Discogs' (open with the linked label + cat#): {short(block)}")
            if REFERENCE_WORD_RE.search(clean) and "](" not in block and kind == "para":
                r.error(f"{where} names a review/video/source with no link in the paragraph: {short(block)}")

            sents = sentences(block)
            for s in sents:
                n = wc(s)
                if n > SENTENCE_FAIL:
                    r.error(f"{where} sentence of {n} words (max {SENTENCE_FAIL}): {short(s)}")
                elif n > SENTENCE_WARN:
                    r.warn(f"{where} sentence of {n} words (flag > {SENTENCE_WARN}): {short(s)}")
                s_clean = strip_quoted(s)
                if CONSENSUS_RE.search(s_clean) and "](" not in s:
                    # link check is on the unstripped sentence text
                    r.warn(f"{where} consensus claim with no link: {short(s)}")

            is_list = all(l.lstrip().startswith(("- ", "* ")) for l in block.split("\n") if l.strip())
            if kind == "para" and not is_list:
                if len(sents) > PARA_MAX_SENTENCES or wc(strip_md(block)) > PARA_MAX_WORDS:
                    r.warn(f"{where} long paragraph ({len(sents)} sentences, {wc(strip_md(block))} words): {short(block, 60)}")

            if block.count("\u2013 ") + block.count(" \u2013") > 0:
                dashes = len(re.findall(r"\s\u2013\s", block))
                if dashes > 1:
                    r.warn(f"{where} {dashes} spaced n-dashes in one {kind} (max 1): {short(block, 60)}")
            if ";" in clean:
                r.warn(f"{where} semicolon in prose (use a full stop): {short(block, 60)}")
            body_no_labels = re.sub(r"\*\*[^*]+:\*\*", "", raw_q)
            body_no_labels = re.sub(r"https?://\S+", "", body_no_labels)
            if re.search(r"[A-Za-z)\"\u201d]: [a-zA-Z\"\u201c]", strip_md(body_no_labels)):
                r.warn(f"{where} mid-sentence colon (restructure or use a full stop): {short(block, 60)}")
            low = clean.lower()
            fl = [p for p in FLOURISH_PHRASES if p in low]
            if fl:
                r.warn(f"{where} flourish phrase(s) {fl}: {short(block, 60)}")
            if not in_buyers and SECOND_PERSON_RE.search(clean):
                r.warn(f"{where} second person outside buyer's guide: {short(block, 60)}")
            if POSITIONAL_RE.search(clean):
                r.warn(f"{where} positional reference ('below'/'above'): {short(block, 60)}")


def check_depth(secs, n_rows, r):
    skip = {"Summary", "References", "Pressing tier summary", "Buyer's guide by budget",
            "Recording history and tape provenance", "Pressings to avoid"}
    words = sum(wc(strip_md(b)) for h, b in secs if h not in skip)
    if n_rows == 0:
        return
    per = words / n_rows
    if per < WORDS_PER_PRESSING_MIN:
        r.warn(f"thin pressing analysis: {words} words across {n_rows} tier rows "
               f"({per:.0f}/pressing, flag < {WORDS_PER_PRESSING_MIN}); check hierarchy completeness too")


def run_style_checks(content, n_rows, r):
    secs = split_sections(content)
    d = dict(secs)
    check_structure(secs, r)
    if "Summary" in d:
        check_summary(d["Summary"], r)
    if "Buyer's guide by budget" in d:
        check_buyers_guide(d["Buyer's guide by budget"], r)
    if "Recording history and tape provenance" in d:
        check_recording_scope(d["Recording history and tape provenance"], r)
    check_prose(secs, r)
    check_depth(secs, n_rows, r)
