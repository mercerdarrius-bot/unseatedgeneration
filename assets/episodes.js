/* Episode behavior shared by every page that shows episodes.
   Safe to load anywhere: each part looks for its own markup and does
   nothing when that markup is absent. */
(function () {
  'use strict';

  /* 1. Stale dates. An upcoming episode prints its air date at build time.
        If that date passes before the site is rebuilt, say "Coming Soon"
        rather than leave a date that is now in the past. */
  var now = Date.now();
  var GRACE = 6 * 60 * 60 * 1000;
  document.querySelectorAll('time[data-airdate]').forEach(function (t) {
    var at = Date.parse(t.getAttribute('datetime'));
    if (!isNaN(at) && now > at + GRACE) t.textContent = 'Coming Soon';
  });

  /* 2. Player. The page ships a thumbnail link to YouTube. The first press
        swaps it for the real player, so YouTube only loads when asked. */
  document.querySelectorAll('.yt[data-yt]').forEach(function (box) {
    var link = box.querySelector('.yt-link');
    if (!link) return;
    link.addEventListener('click', function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return;
      e.preventDefault();
      var frame = document.createElement('iframe');
      frame.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(box.getAttribute('data-yt')) +
        '?autoplay=1&rel=0&playsinline=1';
      frame.title = box.getAttribute('data-title') || 'Episode video';
      frame.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      frame.setAttribute('allowfullscreen', '');
      frame.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      box.textContent = '';
      box.appendChild(frame);
      box.classList.add('is-playing');
      frame.focus();
    });
  });

  /* 3. Archive filter. Buttons report their state with aria-pressed, the
        result is announced, and the choice survives a reload or a shared link. */
  var group = document.querySelector('[data-filter]');
  if (group) {
    var buttons = group.querySelectorAll('button[data-show]');
    var items = document.querySelectorAll('[data-show-item]');
    var status = document.getElementById('filterStatus');
    var names = {};
    buttons.forEach(function (b) { names[b.getAttribute('data-show')] = b.getAttribute('data-name'); });

    var apply = function (show, remember) {
      if (!names[show]) show = 'all';
      var live = 0;
      items.forEach(function (it) {
        var on = show === 'all' || it.getAttribute('data-show-item') === show;
        it.hidden = !on;
        if (on && it.hasAttribute('data-live')) live++;
      });
      document.querySelectorAll('[data-empty]').forEach(function (note) {
        var list = document.getElementById(note.getAttribute('data-empty'));
        note.hidden = !list || list.querySelector('[data-show-item]:not([hidden])') !== null;
      });
      buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-show') === show)); });
      if (status) {
        status.textContent = 'Showing ' + live + (live === 1 ? ' episode' : ' episodes') +
          (show === 'all' ? '' : ' from ' + names[show]) + '.';
      }
      if (remember && window.history && history.replaceState) {
        history.replaceState(null, '', show === 'all' ? location.pathname : location.pathname + '?show=' + show);
      }
    };

    buttons.forEach(function (b) {
      b.addEventListener('click', function () { apply(b.getAttribute('data-show'), true); });
    });
    var asked = new URLSearchParams(location.search).get('show');
    if (asked) apply(asked, false);
  }

  /* 4. Share. Uses the phone's share sheet when there is one, and copies
        the link everywhere else. Either way the result is announced. */
  document.querySelectorAll('[data-share]').forEach(function (btn) {
    var label = btn.querySelector('[data-share-label]') || btn;
    var original = label.textContent;
    var say = document.getElementById('shareStatus');
    var done = function (text) {
      label.textContent = text;
      if (say) say.textContent = text;
      setTimeout(function () { label.textContent = original; }, 2600);
    };
    btn.addEventListener('click', function () {
      var url = location.origin + location.pathname;
      var title = btn.getAttribute('data-share');
      if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(function () {});
      } else if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { done('Link Copied'); }, function () { done('Copy Failed'); });
      } else {
        window.prompt('Copy this link', url);
      }
    });
  });
})();
