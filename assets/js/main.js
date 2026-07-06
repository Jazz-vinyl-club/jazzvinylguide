/* Jazz Vinyl Guide — main.js */

(function () {
  'use strict';

  /* ── TOC: auto-build from h2/h3 in album-content ── */
  const content = document.getElementById('album-content');
  const tocList = document.getElementById('toc-list');

  if (content && tocList) {
    const headings = content.querySelectorAll('h2, h3');

    headings.forEach(function (heading, i) {
      // Assign id if missing
      if (!heading.id) {
        heading.id = 'section-' + i + '-' + heading.textContent
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, '-')
          .replace(/^-|-$/g, '');
      }

      const li = document.createElement('li');
      const a  = document.createElement('a');
      a.href        = '#' + heading.id;
      a.textContent = heading.textContent;

      if (heading.tagName === 'H3') {
        a.style.paddingLeft = '1.5rem';
        a.style.fontSize    = '0.75rem';
      }

      li.appendChild(a);
      tocList.appendChild(li);
    });

    /* ── Active section on scroll ── */
    const tocLinks = tocList.querySelectorAll('a');

    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          tocLinks.forEach(function (link) { link.classList.remove('active'); });
          const active = tocList.querySelector('a[href="#' + entry.target.id + '"]');
          if (active) active.classList.add('active');
        }
      });
    }, { rootMargin: '0px 0px -70% 0px', threshold: 0 });

    headings.forEach(function (h) { observer.observe(h); });
  }

  /* ── Tier table: inject tier badge spans ── */
  document.querySelectorAll('.tier-table tbody tr').forEach(function (row) {
    const firstCell = row.querySelector('td:first-child');
    if (!firstCell) return;

    const text = firstCell.textContent.trim();
    const tierMap = { 'S': 'tier-s', 'A': 'tier-a', 'B': 'tier-b', 'C': 'tier-c', 'D': 'tier-d', 'Avoid': 'tier-avoid' };

    Object.keys(tierMap).forEach(function (tier) {
      if (text === tier || text === '**' + tier + '**') {
        firstCell.innerHTML = '<span class="tier-badge ' + tierMap[tier] + '">' + tier + '</span>';
      }
    });
  });

})();
