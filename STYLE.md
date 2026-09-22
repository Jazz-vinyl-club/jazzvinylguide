# Guide style rules

These rules apply to every guide in `_content/`. `scripts/full_audit.py` enforces what it can (see `scripts/style_checks.py`). The rest is for whoever writes or rewrites a guide, human or model.

## Sentences and punctuation

- Aim for sentences under 25 words. The audit flags anything over 25 and fails anything over 35.
- Use full stops. N-dashes, semicolons and colons are for rare cases, not for joining clauses. At most one spaced n-dash per paragraph.
- No colon to set up a clause ("the answer is simple: ..."). Rewrite as two sentences.
- Paragraphs of four sentences or fewer, and under about 90 words. Split on topic changes.

## Voice

- Plain, factual and independent. State the fact and its source, then stop.
- No rhetorical flourishes or framing devices: "by circumstance rather than design", "what makes X remarkable", "worth knowing", "in other words", "tells a more specific story", contrast constructions built for effect.
- No comparisons without a referent ("even more remarkable" than what?).
- No first person, and no narration of the guide's own research or editing ("I confirmed", "a correction worth making").
- No second person outside the buyer's guide.
- No references to the site, other guides or other albums.
- No positional references ("below", "above"). Sections move and tables are sortable.

## Sourcing

- Hyperlink every reference: reviewers, videos, forum threads, articles, retailer pages.
- Claims of consensus ("widely rated", "generally considered") need a link or get cut.
- When sources disagree, state each with its link. Do not reconcile them with speculation unless a source does.
- A detail taken from a source must be about that exact pressing. A review on a Discogs master page may refer to a different release.

## Structure

Required sections, in this order, with other pressing sections between Recording history and Buyer's guide:

1. `## Summary`: exactly two paragraphs of at least 50 words each, then the "Best ..." lines as bullets.
2. `## Recording history and tape provenance`: the sessions, personnel, and which tapes exist. No chart positions, awards, later reviews or endorsements. No detail about specific reissues. That belongs in the pressing sections.
3. Pressing sections (free headings, e.g. `## Original Columbia pressings (1958)`). Each paragraph opens with the pressing's label and catalogue number, linked to its Discogs release. No "Discogs" link text in prose.
4. `## Pressings to avoid` (optional).
5. `## Buyer's guide by budget`: `$` bands only, no descriptors like "Budget" or "Premium".
6. `## Pressing tier summary`
7. `## References`

## Depth

The audit flags guides with under 150 words of pressing analysis per tier row. A flag means the guide needs research, usually because the hierarchy is missing pressings, not just because the prose is short.
