(function () {
  'use strict';

  // ── TOC for album pages ───────────────────────────────────────────────────
  var content = document.getElementById('album-content');
  var tocList = document.getElementById('toc-list');

  if (content && tocList) {
    var headings = content.querySelectorAll('h2, h3');

    headings.forEach(function (heading, i) {
      if (!heading.id) {
        heading.id = 'section-' + i + '-' + heading.textContent
          .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
      var li = document.createElement('li');
      var a = document.createElement('a');
      a.href = '#' + heading.id;
      a.textContent = heading.textContent;
      if (heading.tagName === 'H3') {
        a.style.paddingLeft = '1.5rem';
        a.style.fontSize = '0.75rem';
      }
      li.appendChild(a);
      tocList.appendChild(li);
    });

    var tocLinks = tocList.querySelectorAll('a');
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          tocLinks.forEach(function (l) { l.classList.remove('active'); });
          var active = tocList.querySelector('a[href="#' + entry.target.id + '"]');
          if (active) active.classList.add('active');
        }
      });
    }, { rootMargin: '0px 0px -70% 0px', threshold: 0 });

    headings.forEach(function (h) { observer.observe(h); });
  }

  // ── Album index search + sort ─────────────────────────────────────────────
  var grid      = document.getElementById('albumGrid');
  var searchEl  = document.getElementById('albumSearch');
  var sortBtns  = document.querySelectorAll('.albums-sort__btn');
  var noResults = document.getElementById('albumsNoResults');

  if (!grid || !searchEl) return;

  var cards = Array.from(grid.querySelectorAll('.album-card'));
  var currentSort = 'default';
  var originalOrder = cards.slice(); // preserve DOM order for "Default"

  function getVal(card, key) {
    return card.dataset[key] || '';
  }

  function applyFilter() {
    var query = searchEl.value.trim().toLowerCase();
    var visible = 0;
    cards.forEach(function (card) {
      var match = !query ||
        getVal(card, 'title').includes(query) ||
        getVal(card, 'artist').includes(query) ||
        getVal(card, 'label').includes(query) ||
        getVal(card, 'year').includes(query);
      card.style.display = match ? '' : 'none';
      if (match) visible++;
    });
    if (noResults) noResults.style.display = visible === 0 ? 'block' : 'none';
  }

  function applySort(key) {
    var sorted;
    if (key === 'default') {
      sorted = originalOrder.slice();
    } else {
      sorted = cards.slice().sort(function (a, b) {
        return getVal(a, key).localeCompare(getVal(b, key));
      });
    }
    sorted.forEach(function (card) { grid.appendChild(card); });
    cards = sorted;
  }

  searchEl.addEventListener('input', applyFilter);

  sortBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      sortBtns.forEach(function (b) { b.classList.remove('active'); });
      btn.classList.add('active');
      currentSort = btn.dataset.sort;
      applySort(currentSort);
      applyFilter();
    });
  });

})();
