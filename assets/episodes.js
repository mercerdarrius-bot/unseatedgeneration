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

  /* Share a link: the phone's share sheet when there is one, the clipboard
     everywhere else. `done` receives the text to show and announce. */
  var shareLink = function (url, title, done) {
    if (navigator.share) {
      navigator.share({ title: title, url: url }).catch(function () {});
    } else if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function () { done('Link Copied'); }, function () { done('Copy Failed'); });
    } else {
      window.prompt('Copy this link', url);
    }
  };

  /* 2. Inline player on an episode page. The page ships a thumbnail link to
        YouTube; the first press swaps it for the real player in place. */
  document.querySelectorAll('.yt[data-yt]').forEach(function (box) {
    var link = box.querySelector('.yt-link');
    if (!link) return;
    link.addEventListener('click', function (e) {
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return;
      e.preventDefault();
      var frame = document.createElement('iframe');
      frame.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(box.getAttribute('data-yt')) +
        '?autoplay=1&rel=0&playsinline=1&enablejsapi=1&origin=https://unseatedgen.org';
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

  /* 3. Share button on an episode page. */
  document.querySelectorAll('[data-share]').forEach(function (btn) {
    var label = btn.querySelector('[data-share-label]') || btn;
    var original = label.textContent;
    var say = document.getElementById('shareStatus');
    btn.addEventListener('click', function () {
      shareLink(location.origin + location.pathname, btn.getAttribute('data-share'), function (text) {
        label.textContent = text;
        if (say) say.textContent = text;
        setTimeout(function () { label.textContent = original; }, 2600);
      });
    });
  });

  /* 4. Player over the page. Any [data-episode] link or button opens that
        episode (or trailer) in a dialog, so a thumbnail plays in one press.
        Without JavaScript, or when opened in a new tab, the link still goes
        to the episode page. Details come from #ugEpisodes, which the build
        writes into each page that needs them. */
  var source = document.getElementById('ugEpisodes');
  var EPISODES = {};
  if (source) {
    try {
      JSON.parse(source.textContent).forEach(function (ep) { EPISODES[ep.key] = ep; });
    } catch (err) { /* leave the plain links working */ }
  }
  if (!Object.keys(EPISODES).length || typeof HTMLDialogElement !== 'function') return;

  var root = document.documentElement;
  var dlg = null;
  var parts = {};
  var opener = null;
  var pushed = false;

  document.querySelectorAll('[data-episode]').forEach(function (t) {
    if (EPISODES[t.getAttribute('data-episode')]) t.setAttribute('aria-haspopup', 'dialog');
  });

  var setText = function (el, text) { el.textContent = text || ''; el.hidden = !text; };

  /* Close through history when the player added an entry, so the phone's
     back gesture closes the player instead of leaving the page. */
  var requestClose = function () {
    if (pushed) history.back();
    else if (dlg && dlg.open) dlg.close();
  };

  var build = function () {
    dlg = document.createElement('dialog');
    dlg.className = 'pd';
    dlg.setAttribute('aria-labelledby', 'pdTitle');
    dlg.innerHTML =
      '<div class="pd-bar">' +
        '<p class="pd-kicker" data-pd="kicker"></p>' +
        '<button class="pd-close" type="button" data-pd="close" aria-label="Close player">' +
          '<span aria-hidden="true">Close</span>' +
          '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" aria-hidden="true"><path d="M5 5l14 14M19 5L5 19"/></svg>' +
        '</button>' +
      '</div>' +
      '<div class="pd-frame" data-pd="frame"></div>' +
      '<div class="pd-info">' +
        '<div>' +
          '<h2 class="pd-title" id="pdTitle" data-pd="title"></h2>' +
          '<p class="pd-meta" data-pd="meta"></p>' +
          '<p class="pd-hook" data-pd="hook"></p>' +
        '</div>' +
        '<div class="pd-actions">' +
          '<button class="pd-btn pd-next" type="button" data-pd="next">Next Episode ' +
            '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg>' +
          '</button>' +
          '<button class="pd-btn" type="button" data-pd="share"><span data-pd="shareLabel">Share Episode</span></button>' +
          '<a class="pd-btn" data-pd="yt" target="_blank" rel="noopener noreferrer">Watch on YouTube<span class="sr-only"> (opens in a new tab)</span></a>' +
        '</div>' +
      '</div>' +
      '<p class="sr-only" role="status" aria-live="polite" data-pd="status"></p>';
    document.body.appendChild(dlg);
    dlg.querySelectorAll('[data-pd]').forEach(function (el) { parts[el.getAttribute('data-pd')] = el; });

    parts.close.addEventListener('click', requestClose);
    dlg.addEventListener('cancel', function (e) { e.preventDefault(); requestClose(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) requestClose(); });
    dlg.addEventListener('close', function () {
      parts.frame.textContent = '';
      root.classList.remove('pd-lock');
      if (pushed) { pushed = false; history.back(); }
      if (opener && document.contains(opener)) opener.focus();
    });
    parts.next.addEventListener('click', function () {
      var key = parts.next.getAttribute('data-key');
      if (key) show(key, true);
    });
    parts.share.addEventListener('click', function () {
      var label = parts.shareLabel;
      shareLink(location.origin + parts.share.getAttribute('data-url'), parts.share.getAttribute('data-title'), function (text) {
        label.textContent = text;
        parts.status.textContent = text;
        setTimeout(function () { label.textContent = 'Share Episode'; }, 2600);
      });
    });
    window.addEventListener('popstate', function () {
      if (!pushed) return;
      pushed = false;
      if (dlg.open) dlg.close();
    });
  };

  var show = function (key, fromNext) {
    var ep = EPISODES[key];
    if (!ep) return false;
    if (!dlg) build();

    parts.kicker.textContent = ep.kicker || '';
    parts.title.textContent = ep.title;
    setText(parts.meta, ep.meta);
    setText(parts.hook, ep.hook);
    dlg.classList.toggle('is-vertical', !!ep.vertical);

    parts.frame.textContent = '';
    if (ep.video) {
      var v = document.createElement('video');
      v.src = ep.video;
      if (ep.poster) v.poster = ep.poster;
      v.controls = true;
      v.playsInline = true;
      v.setAttribute('playsinline', '');
      v.setAttribute('aria-label', ep.title);
      parts.frame.appendChild(v);
      var started = v.play();
      if (started && started.catch) started.catch(function () {});
    } else {
      var f = document.createElement('iframe');
      f.src = 'https://www.youtube-nocookie.com/embed/' + encodeURIComponent(ep.youtube) + '?autoplay=1&rel=0&playsinline=1&enablejsapi=1&origin=https://unseatedgen.org';
      f.title = (ep.kicker ? ep.kicker + ', ' : '') + ep.title;
      f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
      f.setAttribute('allowfullscreen', '');
      f.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
      parts.frame.appendChild(f);
    }

    var nxt = ep.next && EPISODES[ep.next];
    parts.next.hidden = !nxt;
    if (nxt) {
      parts.next.setAttribute('data-key', nxt.key);
      parts.next.setAttribute('aria-label', 'Next episode: ' + nxt.title);
    }
    parts.share.hidden = !ep.page;
    if (ep.page) {
      parts.share.setAttribute('data-url', ep.page);
      parts.share.setAttribute('data-title', ep.title);
    }
    parts.yt.hidden = !ep.youtube;
    if (ep.youtube) parts.yt.href = 'https://www.youtube.com/watch?v=' + encodeURIComponent(ep.youtube);

    if (!dlg.open) {
      dlg.showModal();
      root.classList.add('pd-lock');
      if (window.history && history.pushState) { history.pushState({ pd: true }, ''); pushed = true; }
    }
    if (fromNext) {
      parts.status.textContent = 'Now playing: ' + ep.title;
      (nxt ? parts.next : parts.close).focus();
    } else {
      parts.close.focus();
    }
    return true;
  };

  /* Capture phase, so the press opens the player before any page-transition
     handler on the same link can navigate away. */
  document.addEventListener('click', function (e) {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    var t = e.target.closest ? e.target.closest('[data-episode]') : null;
    if (!t || (dlg && dlg.contains(t))) return;
    opener = t;
    if (show(t.getAttribute('data-episode'), false)) {
      e.preventDefault();
      e.stopPropagation();
    }
  }, true);
})();
