/* Page furniture for the generated pages (/watch/ and episode pages):
   menu, scroll progress, page transition, and entrance motion.
   Hand-built pages carry their own copies of these inline. */
(function () {
  'use strict';
  var calm = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* Mobile menu: a real button that reports whether the menu is open. */
  var burger = document.getElementById('hamburger');
  var links = document.getElementById('navLinks');
  if (burger && links) {
    var setOpen = function (open) {
      links.classList.toggle('open', open);
      burger.setAttribute('aria-expanded', String(open));
      burger.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    };
    burger.addEventListener('click', function () { setOpen(!links.classList.contains('open')); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && links.classList.contains('open')) { setOpen(false); burger.focus(); }
    });
  }

  /* Watch menu: hover opens it for a mouse; this adds click, keyboard, and
     the state screen readers hear. On small screens it is always open. */
  var group = document.querySelector('.nav-group');
  if (group) {
    var gbtn = group.querySelector('.nav-group-btn');
    var small = window.matchMedia('(max-width: 1024px)');
    var setGroup = function (open) {
      group.classList.toggle('open', open);
      gbtn.setAttribute('aria-expanded', String(open || small.matches));
    };
    var syncGroup = function () { gbtn.tabIndex = small.matches ? -1 : 0; setGroup(false); };
    syncGroup();
    small.addEventListener('change', syncGroup);
    gbtn.addEventListener('click', function (e) { e.stopPropagation(); setGroup(!group.classList.contains('open')); });
    group.addEventListener('mouseenter', function () { gbtn.setAttribute('aria-expanded', 'true'); });
    group.addEventListener('mouseleave', function () { setGroup(false); });
    group.addEventListener('focusout', function (e) { if (!group.contains(e.relatedTarget)) setGroup(false); });
    document.addEventListener('click', function (e) { if (!group.contains(e.target)) setGroup(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && group.classList.contains('open')) { setGroup(false); gbtn.focus(); }
    });
  }

  /* Scroll progress */
  var bar = document.getElementById('progressBar');
  if (bar) {
    window.addEventListener('scroll', function () {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? h.scrollTop / max * 100 : 0) + '%';
    }, { passive: true });
  }

  /* Page transition between pages of this site. Skipped for reduced motion
     and for clicks that mean "new tab". */
  var veil = document.getElementById('pageTransition');
  if (veil && !calm) {
    document.querySelectorAll('a[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      if (!href || href.charAt(0) === '#' || /^(https?:|mailto:|tel:)/.test(href) || a.target === '_blank') return;
      a.addEventListener('click', function (e) {
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button === 1) return;
        e.preventDefault();
        veil.classList.add('exit');
        setTimeout(function () { window.location.href = href; }, 500);
      });
    });
    window.addEventListener('pageshow', function () {
      veil.classList.remove('exit');
      veil.classList.add('enter');
      setTimeout(function () { veil.classList.remove('enter'); }, 600);
    });
  }

  /* Entrance motion */
  document.querySelectorAll('.word-inner').forEach(function (w, i) {
    setTimeout(function () { w.classList.add('animate'); }, 250 + i * 130);
  });
  document.querySelectorAll('.fade').forEach(function (el, i) {
    setTimeout(function () { el.classList.add('animate'); }, 700 + i * 160);
  });
  var reveals = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window) {
    var seen = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add('visible'); seen.unobserve(en.target); }
      });
    }, { threshold: 0.08 });
    reveals.forEach(function (el) { seen.observe(el); });
  } else {
    reveals.forEach(function (el) { el.classList.add('visible'); });
  }
})();
