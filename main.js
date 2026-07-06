(function () {
  'use strict';

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
})();
