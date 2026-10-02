#!/usr/bin/env python3
"""Build every episode surface on unseatedgen.org from one list.

    python3 _tools/build.py

Reads   _tools/episodes.json   (the only file you edit to add an episode)
Writes  /watch/index.html                     the archive
        /<show>/.../episode-N/index.html       one page per live episode
        the marked regions inside index.html, series/, season1/, context/
        sitemap.xml and robots.txt

An episode is "live" once it has a "youtube" id. Until then it shows as
upcoming with its air date. See _tools/README.md for the full field list.

The folder name starts with an underscore so GitHub Pages never serves it.
"""

import hashlib
import html
import json
import re
import sys
from datetime import date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "_tools" / "episodes.json"

FONTS = ("https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400;1,700"
         "&family=Barlow:wght@300;400;500;600;700&family=Barlow+Condensed:wght@400;600;700;800&display=swap")
PLAY = '<svg width="{0}" height="{0}" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>'
ARROW = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
         'aria-hidden="true"><path d="M5 12h14M12 5l7 7-7 7"/></svg>')
ORDINALS = ["Zero", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]

# Hand-built pages that belong in the sitemap. Episode pages and /watch/ are added by the build.
STATIC_PAGES = ["/", "/watch/", "/series/", "/season1/", "/context/", "/mission/", "/about/", "/get-involved/"]


# ---------------------------------------------------------------- helpers

def esc(text):
    return html.escape(str(text), quote=True)


def two(n):
    return f"{n:02d}"


def ordinal(n):
    return ORDINALS[n] if n < len(ORDINALS) else str(n)


def asset(path):
    """Asset URL with a content hash, so a changed file is never served stale."""
    digest = hashlib.sha1((ROOT / path.lstrip("/")).read_bytes()).hexdigest()[:8]
    return f"{path}?v={digest}"


def emphasize(ep):
    """Title as HTML, with the episode's one emphasized word in gold italics."""
    title = esc(ep["title"])
    word = ep.get("emphasis")
    if word and esc(word) in title:
        title = title.replace(esc(word), f"<em>{esc(word)}</em>", 1)
    return title


def runtime_parts(runtime):
    parts = [int(p) for p in runtime.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    return parts  # h, m, s


def runtime_minutes(runtime):
    h, m, s = runtime_parts(runtime)
    return max(1, round(h * 60 + m + s / 60))


def runtime_iso(runtime):
    h, m, s = runtime_parts(runtime)
    return "PT" + (f"{h}H" if h else "") + f"{m}M{s}S"


def day_short(d):   # Tue, Oct 6
    return f"{d:%a}, {d:%b} {d.day}"


def day_medium(d):  # Sep 22, 2026
    return f"{d:%b} {d.day}, {d.year}"


def day_long(d):    # September 22, 2026
    return f"{d:%B} {d.day}, {d.year}"


def when(ep, style="auto"):
    """<time> for an episode. Upcoming dates carry data-airdate so the page can
    stop showing a date that has already passed (see assets/episodes.js)."""
    d = ep["air"].date()
    stamp = ep["air"].isoformat()
    if ep["live"]:
        text = day_long(d) if style == "long" else day_medium(d)
        return f'<time datetime="{stamp}">{text}</time>'
    return f'<time datetime="{stamp}" data-airdate>{day_short(d)}</time>'


def verse(ep):
    return f'{esc(ep["scripture"])} · {esc(ep["translation"])}'


# ---------------------------------------------------------------- data

def load():
    raw = DATA_FILE.read_text(encoding="utf-8")
    problems = []
    if chr(0x2014) in raw:
        problems.append("episodes.json contains an em dash. The brand rule is no em dashes; use a period or comma.")
    data = json.loads(raw)
    zone = ZoneInfo(data["timezone"])
    hh, mm = (int(x) for x in data["premiereTime"].split(":"))
    seen = set()

    for ep in data["episodes"]:
        name = f'{ep.get("show")} #{ep.get("number")} "{ep.get("title", "")}"'
        for field in ("show", "number", "title", "date", "scripture", "translation"):
            if not ep.get(field):
                problems.append(f"{name}: missing \"{field}\"")
        if ep.get("show") not in data["shows"]:
            problems.append(f"{name}: unknown show")
            continue
        show = data["shows"][ep["show"]]
        if "{season}" in show["episodePath"]:
            if not ep.get("season"):
                problems.append(f"{name}: this show needs a \"season\"")
                continue
            if f'{ep["show"]}-{ep["season"]}' not in data["seasons"]:
                problems.append(f'{name}: add "{ep["show"]}-{ep["season"]}" to "seasons"')
                continue
        key = (ep["show"], ep.get("season"), ep["number"])
        if key in seen:
            problems.append(f"{name}: duplicate episode number")
        seen.add(key)
        try:
            day = date.fromisoformat(ep["date"])
        except (ValueError, KeyError, TypeError):
            problems.append(f'{name}: "date" must look like 2026-10-06')
            continue

        ep["live"] = bool(ep.get("youtube"))
        ep["air"] = datetime.combine(day, time(hh, mm), tzinfo=zone)
        ep["show_name"] = show["name"]
        ep["path"] = show["episodePath"].format(season=ep.get("season"), number=ep["number"])
        ep["season_info"] = data["seasons"].get(f'{ep["show"]}-{ep.get("season")}')
        ep["label"] = (f'Season {ep["season"]} · ' if ep.get("season") else "") + f'Episode {ep["number"]}'

        if ep["live"]:
            for field in ("runtime", "hook", "summary"):
                if not ep.get(field):
                    problems.append(f"{name}: a live episode needs \"{field}\"")
            if ep.get("runtime") and not re.fullmatch(r"(\d+:)?\d{1,2}:\d{2}", ep["runtime"]):
                problems.append(f'{name}: "runtime" must look like 26:44')
            thumb = ep.get("thumb")
            if thumb and not (ROOT / thumb.lstrip("/")).exists():
                problems.append(f"{name}: thumbnail file {thumb} does not exist")
            # No local artwork: use the thumbnail YouTube already serves for the video.
            ep["image"] = thumb or f'https://i.ytimg.com/vi/{ep["youtube"]}/maxresdefault.jpg'
            ep["image_abs"] = ep["image"] if ep["image"].startswith("http") else data["site"] + ep["image"]
            ep["watch_url"] = f'https://www.youtube.com/watch?v={ep["youtube"]}'

    if problems:
        print("Cannot build. Fix these in _tools/episodes.json:\n  - " + "\n  - ".join(problems))
        sys.exit(1)

    eps = data["episodes"]
    data["live"] = sorted((e for e in eps if e["live"]), key=lambda e: e["air"], reverse=True)
    data["upcoming"] = sorted((e for e in eps if not e["live"]), key=lambda e: e["air"])
    return data


def of_show(data, show, season=None):
    """Every episode of a show (and season), in episode order."""
    return sorted((e for e in data["episodes"] if e["show"] == show and (season is None or e.get("season") == season)),
                  key=lambda e: (e.get("season") or 0, e["number"]))


def latest_live(data, show, season=None):
    live = [e for e in data["live"] if e["show"] == show and (season is None or e.get("season") == season)]
    return live[0] if live else None


# ---------------------------------------------------------------- shared page furniture

def head(data, title, description, path, image, og_type="website", extra=""):
    url = data["site"] + path
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(description)}" />
  <link rel="canonical" href="{url}" />
  <meta property="og:type" content="{og_type}" />
  <meta property="og:site_name" content="Unseated Generation" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(description)}" />
  <meta property="og:url" content="{url}" />
  <meta property="og:image" content="{esc(image)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <script>document.documentElement.className = 'js';</script>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="{FONTS}" rel="stylesheet" />
  <link rel="stylesheet" href="{asset('/assets/episodes.css')}" />{extra}
</head>
<body>
  <!-- Built by _tools/build.py from _tools/episodes.json. Edit those, not this file. -->
  <a class="skip-link" href="#main">Skip to content</a>
  <div class="progress-bar" id="progressBar"></div>
  <div class="page-transition" id="pageTransition"></div>
"""


def nav(active):
    items = [("/watch/", "Watch"), ("/mission", "The Mission"), ("/about", "About"),
             ("/series", "The Unseated Series"), ("/context", "Context Matters"), ("/get-involved/", "Get Involved")]
    rows = []
    for href, label in items:
        mark = ""
        if href == active:
            mark = ' class="active"' + (' aria-current="page"' if href == "/watch/" else "")
        rows.append(f'      <li><a href="{href}"{mark}>{label}</a></li>')
    return f"""  <nav class="site-nav" aria-label="Main">
    <a href="/" class="nav-logo" aria-label="Unseated Generation home">
      <div class="nav-wordmark">UN/<span>SEATED</span></div>
      <div class="nav-sub">Generation</div>
    </a>
    <ul class="nav-center" id="navLinks">
{chr(10).join(rows)}
    </ul>
    <button class="hamburger" id="hamburger" type="button" aria-label="Open menu" aria-expanded="false" aria-controls="navLinks">
      <span></span><span></span><span></span>
    </button>
  </nav>
"""


def footer(data):
    socials = [("Instagram", "https://www.instagram.com/unseatedgen/"), ("Facebook", "https://www.facebook.com/unseatedgeneration"),
               ("TikTok", "https://www.tiktok.com/@unseatedgen"), ("YouTube", data["channel"])]
    ext = 'target="_blank" rel="noopener noreferrer"'
    column = "\n".join(f'          <li><a href="{u}" {ext}>{n}</a></li>' for n, u in socials)
    row = "\n".join(f'        <a href="{u}" {ext}>{n}</a>' for n, u in socials)
    return f"""  <footer>
    <div class="footer-top">
      <div class="footer-brand">
        <div class="wordmark">UN/<span>SEATED</span></div>
        <div class="tagline">Generation · Called. Refined. Sent.</div>
        <p>Unseated Generation is a faith-based ministry. We confront the systems, mindsets, and patterns that prevent maturity and limit kingdom impact, and we work to express the love of Christ in tangible ways. Called. Refined. Sent.</p>
      </div>
      <div>
        <div class="footer-col-head">Content</div>
        <ul class="footer-links">
          <li><a href="/watch/">All Episodes</a></li>
          <li><a href="/series">The Unseated Series</a></li>
          <li><a href="/context">Context Matters</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-head">Platform</div>
        <ul class="footer-links">
          <li><a href="/mission">The Mission</a></li>
          <li><a href="/about">About</a></li>
          <li><a href="/get-involved/">Get Involved</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-head">Follow</div>
        <ul class="footer-links">
{column}
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p class="footer-copy">© {date.today().year} Unseated Generation. All rights reserved.</p>
      <div class="footer-socials">
{row}
      </div>
    </div>
  </footer>

  <script src="{asset('/assets/chrome.js')}" defer></script>
  <script src="{asset('/assets/episodes.js')}" defer></script>
</body>
</html>
"""


def player(ep, eager=False):
    """Thumbnail that becomes the YouTube player on the first press."""
    name = f'Episode {ep["number"]}: {ep["title"]}'
    minutes = runtime_minutes(ep["runtime"])
    loading = 'fetchpriority="high"' if eager else 'loading="lazy"'
    return f"""<div class="yt" data-yt="{esc(ep['youtube'])}" data-title="{esc(ep['show_name'])}, {esc(name)}">
          <a class="yt-link" href="{ep['watch_url']}" aria-label="Play {esc(name)}, {minutes} minutes">
            <img src="{esc(ep['image'])}" alt="" width="1280" height="720" {loading} />
            <span class="yt-play" aria-hidden="true">{PLAY.format(30)}</span>
            <span class="yt-cap" aria-hidden="true"><b>Play</b> {esc(ep['runtime'])}</span>
          </a>
        </div>"""


def kicker(ep, season_title=False):
    """Gold show name, then where the episode sits in it."""
    where = ep["label"]
    if season_title and ep.get("season_info"):
        where = f'Season {ep["season"]}: {esc(ep["season_info"]["title"])} · Episode {ep["number"]}'
    return f'<p class="kicker"><b>{esc(ep["show_name"])}</b> · {where}</p>'


# ---------------------------------------------------------------- /watch/

def build_watch(data):
    live, upcoming = data["live"], data["upcoming"]
    newest = live[0] if live else None
    desc = ("Every episode of The Unseated Series and Context Matters in one place. "
            "New teaching premieres Tuesdays at 6 PM ET.")
    image = newest["image_abs"] if newest else data["site"] + "/Photos/S1E1-Thumbnail.jpg"

    out = [head(data, "Watch · Unseated Generation", desc, "/watch/", image), nav("/watch/")]
    out.append("""  <main id="main">
    <section class="page-hero">
      <div class="page-hero-bg"></div>
      <div class="page-hero-word" aria-hidden="true">Watch</div>
      <div class="page-hero-inner">
        <div class="eyebrow"><span>Watch</span></div>
        <h1 class="page-title">
          <span class="word"><span class="word-inner">Every</span></span> <span class="word"><span class="word-inner">Episode.</span></span><br>
          <span class="word"><span class="word-inner">One</span></span> <span class="word"><span class="word-inner gold-shimmer">Place.</span></span>
        </h1>
        <p class="page-desc fade">The Unseated Series and Context Matters, together. <strong>New teaching premieres Tuesdays at 6 PM ET.</strong></p>
      </div>
    </section>
""")

    if newest:
        out.append(f"""
    <section class="w-latest" aria-labelledby="latestTitle">
      <div class="w-latest-inner">
        <div class="reveal">
        {player(newest, eager=True)}
        </div>
        <div class="w-latest-body reveal reveal-2">
          <div class="eyebrow"><span>Latest Episode</span></div>
          {kicker(newest)}
          <h2 class="ep-title" id="latestTitle">{emphasize(newest)}</h2>
          <div class="meta"><span>{verse(newest)}</span><i></i><span>{runtime_minutes(newest['runtime'])} min</span><i></i><span>{when(newest)}</span></div>
          <p class="w-desc">{esc(newest['hook'])}</p>
          <a class="text-link" href="{newest['path']}">Episode Details {ARROW}</a>
        </div>
      </div>
    </section>
""")

    # Archive grid with the series filter
    counts = {key: sum(1 for e in live if e["show"] == key) for key in data["shows"]}
    buttons = [f'<button type="button" data-show="all" data-name="all series" aria-pressed="true">All <span>{len(live)}</span></button>']
    for key, show in data["shows"].items():
        buttons.append(f'<button type="button" data-show="{key}" data-name="{esc(show["name"])}" aria-pressed="false">'
                       f'{esc(show["name"])} <span>{counts[key]}</span></button>')
    cards = []
    for ep in live:
        cards.append(f"""        <li class="reveal" data-show-item="{ep['show']}" data-live>
          <a class="ep-card" href="{ep['path']}">
            <div class="ep-card-thumb">
              <img src="{esc(ep['image'])}" alt="" width="1280" height="720" loading="lazy" />
              <span class="ep-card-play" aria-hidden="true">{PLAY.format(15)}</span>
              <span class="ep-card-time"><span class="sr-only">Runtime </span>{esc(ep['runtime'])}</span>
            </div>
            {kicker(ep)}
            <h3>{esc(ep['title'])}</h3>
            <p class="ep-card-foot">{esc(ep['scripture'])} · {when(ep)}</p>
          </a>
        </li>""")
    few = " few" if len(live) <= 2 else ""
    out.append(f"""
    <section class="w-archive" aria-labelledby="archiveTitle">
      <div class="w-head">
        <div class="reveal">
          <div class="eyebrow"><span>The Archive</span></div>
          <h2 class="h2" id="archiveTitle">Browse the <em>Teaching.</em></h2>
        </div>
        <div class="filter reveal reveal-2" role="group" aria-label="Filter episodes by series" data-filter>
          {(chr(10) + '          ').join(buttons)}
        </div>
      </div>
      <p class="sr-only" id="filterStatus" role="status" aria-live="polite"></p>
      <ul class="ep-grid{few}" id="epGrid">
{chr(10).join(cards)}
      </ul>
      <p class="w-empty" data-empty="epGrid" hidden>No episodes from this series yet. The first one is on the calendar below.</p>
    </section>
""")

    if upcoming:
        rows = []
        for ep in upcoming:
            rows.append(f"""        <li class="up-row reveal" data-show-item="{ep['show']}">
          <div class="up-date">{when(ep)}</div>
          <div>
            {kicker(ep)}
            <h3>{esc(ep['title'])}</h3>
            <p class="up-verse">{verse(ep)}</p>
          </div>
          <span class="up-tag">Upcoming</span>
        </li>""")
        out.append(f"""
    <section class="w-up" aria-labelledby="upTitle">
      <div class="w-head">
        <div class="reveal">
          <div class="eyebrow"><span>On the Calendar</span></div>
          <h2 class="h2" id="upTitle">Coming <em>Up.</em></h2>
        </div>
        <p class="w-up-note reveal reveal-2">Episodes premiere on YouTube, Tuesdays at 6 PM ET, and land here the same night.</p>
      </div>
      <ul class="up-list" id="upList">
{chr(10).join(rows)}
      </ul>
      <p class="w-empty" data-empty="upList" hidden>Nothing scheduled for this series yet.</p>
    </section>
""")

    out.append("  </main>\n\n")
    out.append(footer(data))
    write("watch/index.html", "".join(out))


# ---------------------------------------------------------------- episode pages

def step_card(ep, direction, extra_class=""):
    """Previous / next card under an episode. Live episodes link; upcoming ones show their date."""
    body = f"""<div class="e-step-dir">{direction}</div>
          <h3>{esc(ep['title'])}</h3>
          <p>{esc(ep['show_name'])} · {ep['label']}{'' if ep['live'] else ' · ' + when(ep)}</p>"""
    cls = f"e-step{extra_class}"
    if ep["live"]:
        return f'<a class="{cls}" href="{ep["path"]}">\n          {body}\n        </a>'
    return f'<div class="{cls}">\n          {body}\n        </div>'


def build_episode(data, ep):
    show = data["shows"][ep["show"]]
    siblings = of_show(data, ep["show"])
    at = siblings.index(ep)
    earlier = next((e for e in reversed(siblings[:at]) if e["live"]), None)
    later = siblings[at + 1] if at + 1 < len(siblings) else None
    elsewhere = next((e for e in data["live"] if e["show"] != ep["show"]), None)

    title = f'{ep["title"]} · {ep["show_name"]}'
    description = ep["hook"]
    ld = {
        "@context": "https://schema.org", "@type": "VideoObject",
        "name": f'{ep["title"]} ({ep["show_name"]}, {ep["label"].replace(" · ", ", ")})',
        "description": " ".join(ep["summary"]),
        "thumbnailUrl": [ep["image_abs"]],
        "uploadDate": ep["air"].isoformat(),
        "duration": runtime_iso(ep["runtime"]),
        "embedUrl": f'https://www.youtube.com/embed/{ep["youtube"]}',
        "contentUrl": ep["watch_url"],
        "publisher": {"@type": "Organization", "name": "Unseated Generation", "url": data["site"]},
    }
    extra = '\n  <script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>"

    crumbs = [f'<li><a href="/watch/">Watch</a></li>', f'<li><a href="{show["home"]}">{esc(show["name"])}</a></li>']
    if ep.get("season_info"):
        crumbs.append(f'<li><a href="{ep["season_info"]["home"]}">Season {ep["season"]}</a></li>')
    crumbs.append(f'<li aria-current="page">Episode {ep["number"]}</li>')

    passage = esc(ep["scripture"]) + f'<span>{esc(ep["translation"])}</span>'
    if ep.get("quote"):
        passage = esc(ep["scripture"]) + f'<span>"{esc(ep["quote"])}" · {esc(ep["translation"])}</span>'
    series_line = f'<a href="{show["home"]}">{esc(show["name"])}</a>'
    if ep.get("season_info"):
        series_line += f'<span>Season {ep["season"]}: {esc(ep["season_info"]["title"])}</span>'

    steps = []
    left = earlier or elsewhere
    if left:
        steps.append(step_card(left, "Previous Episode" if earlier else "Also Streaming"))
    if later:
        steps.append(step_card(later, "Next Episode" if later["live"] else "Up Next", " is-next"))
    paragraphs = "\n".join(f"          <p>{esc(p)}</p>" for p in ep["summary"])

    page = [head(data, title, description, ep["path"], ep["image_abs"], og_type="video.other", extra=extra),
            nav("/series" if ep["show"] == "series" else "/context")]
    page.append(f"""  <main id="main">
    <section class="e-top">
      <div class="e-wrap">
        <nav class="crumbs" aria-label="Breadcrumb">
          <ol>
            {(chr(10) + '            ').join(crumbs)}
          </ol>
        </nav>
        {player(ep, eager=True)}
        <div class="e-head">
          <div>
            {kicker(ep, season_title=True)}
            <h1 class="e-title">{emphasize(ep)}</h1>
            <div class="meta"><span>{verse(ep)}</span><i></i><span>{runtime_minutes(ep['runtime'])} min</span><i></i><span>{when(ep, 'long')}</span></div>
          </div>
          <div class="e-actions">
            <a class="btn btn-ghost" href="{ep['watch_url']}" target="_blank" rel="noopener noreferrer">Watch on YouTube<span class="sr-only"> (opens in a new tab)</span></a>
            <button class="btn btn-ghost" type="button" data-share="{esc(ep['title'])}"><span data-share-label>Share Episode</span></button>
            <span class="sr-only" id="shareStatus" role="status" aria-live="polite"></span>
          </div>
        </div>
      </div>
    </section>

    <section class="e-body" aria-labelledby="aboutTitle">
      <div class="e-body-inner">
        <div class="e-summary reveal">
          <div class="eyebrow"><span id="aboutTitle">About This Episode</span></div>
{paragraphs}
        </div>
        <aside class="e-aside reveal reveal-2" aria-label="Episode details">
          <dl>
            <div><dt>Scripture</dt><dd>{passage}</dd></div>
            <div><dt>Series</dt><dd>{series_line}</dd></div>
            <div><dt>Runtime</dt><dd>{runtime_minutes(ep['runtime'])} minutes</dd></div>
            <div><dt>Premiered</dt><dd>{when(ep, 'long')}</dd></div>
          </dl>
        </aside>
      </div>
    </section>

    <section class="e-more" aria-labelledby="moreTitle">
      <div class="e-more-head">
        <div class="reveal">
          <div class="eyebrow"><span>Keep Watching</span></div>
          <h2 class="h2" id="moreTitle">More <em>Teaching.</em></h2>
        </div>
        <a class="text-link reveal reveal-2" href="/watch/">All Episodes {ARROW}</a>
      </div>
      <div class="e-pair reveal">
        {(chr(10) + '        ').join(steps)}
      </div>
    </section>
  </main>

""")
    page.append(footer(data))
    write(ep["path"].strip("/") + "/index.html", "".join(page))


# ---------------------------------------------------------------- regions inside hand-built pages

def region(path, name, content):
    """Swap the HTML between <!-- BUILD:name --> and <!-- /BUILD:name -->."""
    file = ROOT / path
    text = file.read_text(encoding="utf-8")
    pattern = re.compile(rf"(?P<open>[ \t]*<!-- BUILD:{re.escape(name)} -->\n).*?(?P<close>[ \t]*<!-- /BUILD:{re.escape(name)} -->)", re.S)
    if len(pattern.findall(text)) != 1:
        print(f"Cannot build: {path} must contain exactly one <!-- BUILD:{name} --> ... <!-- /BUILD:{name} --> pair.")
        sys.exit(1)
    new = pattern.sub(lambda m: m.group("open") + content.rstrip("\n") + "\n" + m.group("close"), text)
    if new != text:
        file.write_text(new, encoding="utf-8")
        CHANGED.append(f"{path} [{name}]")


def home_series(data):
    """Homepage: newest Unseated Series episode, then what is next."""
    ep = latest_live(data, "series")
    nxt = [e for e in data["upcoming"] if e["show"] == "series"][:3]
    out = []
    if ep:
        out.append(f"""    <a href="{ep['path']}" class="ep-feature reveal">
      <div class="ep-feature-media">
        <img src="{esc(ep['image'])}" alt="" />
        <div class="ep-feature-veil"></div>
        <div class="ep-play" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="#D4A840"><path d="M8 5v14l11-7z"/></svg></div>
      </div>
      <div class="ep-feature-body">
        <span class="ep-live">Now Streaming</span>
        <div class="ep-feature-num">{ep['label']} · {runtime_minutes(ep['runtime'])} min</div>
        <h3 class="ep-feature-title">{esc(ep['title'])}</h3>
        <div class="ep-feature-verse">{verse(ep)}</div>
        <span class="ep-feature-cta">Watch Episode {ep['number']} {ARROW}</span>
      </div>
    </a>
""")
    if nxt:
        rows = "\n".join(f"""        <li class="ep-row">
          <span class="ep-row-num">{two(e['number'])}</span>
          <div>
            <h4 class="ep-row-title">{esc(e['title'])}</h4>
            <span class="ep-row-verse">{verse(e)}</span>
          </div>
          <span class="ep-row-status">{when(e)}</span>
        </li>""" for e in nxt)
        out.append(f"""
    <div class="ep-next reveal reveal-delay-2">
      <div class="ep-next-head">
        <div class="series-eyebrow-line"></div>
        <span class="series-eyebrow-text">Up Next</span>
      </div>
      <ul class="ep-list">
{rows}
      </ul>
    </div>
""")
    region("index.html", "home-series", "".join(out))


def home_context(data):
    """Homepage: newest Context Matters episode, then the next two on the calendar."""
    newest = latest_live(data, "context")
    upcoming = [e for e in data["upcoming"] if e["show"] == "context"]
    older = [e for e in data["live"] if e["show"] == "context" and e is not newest]
    picks = ([newest] if newest else []) + upcoming[:2]
    picks += older[: max(0, 3 - len(picks))]
    cards = []
    for e in picks:
        line = (f'"{esc(e["quote"])}" · ' if e.get("quote") else "") + esc(e["scripture"])
        inner = f"""          <div class="ctx-card-shine"></div>
          <div class="ctx-card-top"><div class="ctx-ep">Episode {two(e['number'])}</div><div class="ctx-status {'live' if e['live'] else 'coming'}">{'Watch Now' if e['live'] else when(e)}</div></div>
          <div class="ctx-title">{esc(e['title'])}</div>
          <div class="ctx-verse">{line}</div>"""
        if e["live"]:
            cards.append(f'        <a class="ctx-card" href="{e["path"]}">\n{inner}\n          <div class="ctx-arrow" aria-hidden="true">→</div>\n        </a>')
        else:
            cards.append(f'        <div class="ctx-card">\n{inner}\n        </div>')
    region("index.html", "home-context", "\n".join(cards))


def season_page(data, show, season, path):
    """/season1/: hero status, the featured (newest) episode, and the full lineup."""
    eps = of_show(data, show, season)
    newest = latest_live(data, show, season)
    first = next((e for e in eps if e["live"]), None)
    nxt = next((e for e in eps if not e["live"]), None)
    count = f"{len(eps)} Episodes"

    # Hero meta and buttons
    if newest:
        status = "<span><b>Now Streaming</b></span>"
        actions = (f'        <a href="{first["path"]}" class="btn-s1 gold magnetic"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg> Watch Episode {first["number"]}</a>\n'
                   '        <a href="#trailer" class="btn-s1 ghost magnetic" data-trailer-cta>Watch the Trailer</a>')
    else:
        status = f"<span>Premieres <b>{when(eps[0])}</b></span>"
        actions = ('        <a href="#trailer" class="btn-s1 gold magnetic" data-trailer-cta><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg> Watch the Trailer</a>')
    region(path, "season-hero", f"""      <div class="s1-meta" id="heroMeta">
        <span>Season {ordinal(season)}</span><i></i>
        <span>{count}</span><i></i>
        {status}
      </div>
      <div class="s1-actions" id="pageActions">
{actions}
      </div>""")

    # Featured episode
    if newest:
        label = "The Series Begins Here" if newest["number"] == 1 else "Latest Episode"
        region(path, "season-feature", f"""    <div class="s1-feature-inner">
      <a class="s1-feature-art reveal" href="{newest['path']}" aria-label="Watch Episode {newest['number']}: {esc(newest['title'])}">
        <img src="{esc(newest['image'])}" alt="" />
        <div class="s1-feature-badge">Episode {two(newest['number'])}</div>
        <span class="s1-feature-play" aria-hidden="true"><svg width="20" height="20" viewBox="0 0 24 24" fill="#D4A840"><path d="M8 5v14l11-7z"/></svg></span>
      </a>
      <div class="s1-feature-body reveal reveal-delay-2">
        <div class="s1-feature-num" aria-hidden="true">{two(newest['number'])}</div>
        <div class="s1-label on-light">{label}</div>
        <h2 class="s1-feature-title">{emphasize(newest)}</h2>
        <div class="s1-feature-meta">
          <span class="s1-status"><b>Now Streaming</b></span><i></i>
          <span>{verse(newest)}</span><i></i>
          <span>{runtime_minutes(newest['runtime'])} min</span>
        </div>
        <p class="s1-feature-desc">{esc(newest['hook'])}</p>
        <a class="btn-ep" href="{newest['path']}">Watch Episode {newest['number']}</a>
      </div>
    </div>""")

    # Lineup: every episode of the season, in order, each in its current state
    middle = f"<span>Next Episode <b>{when(nxt)}</b></span>" if nxt else "<span><b>Season Complete</b></span>"
    cards = []
    for i, e in enumerate(eps):
        tag = '<span class="s1-card-tag live">Watch Now</span>' if e["live"] else f'<span class="s1-card-tag">{when(e)}</span>'
        inner = f"""        <div class="s1-card-bg ep{(e['number'] - 1) % 4 + 1}"></div>
        <div class="s1-card-num" aria-hidden="true">{two(e['number'])}</div>
        <div class="s1-card-body">
          <div class="s1-card-ep">Episode {two(e['number'])}</div>
          <h3>{esc(e['title'])}</h3>
          {tag}
        </div>"""
        delay = f" reveal-delay-{i % 3 + 1}"
        if e["live"]:
            cards.append(f'      <a class="s1-card reveal{delay}" href="{e["path"]}">\n{inner}\n      </a>')
        else:
            cards.append(f'      <article class="s1-card reveal{delay}">\n{inner}\n      </article>')
    region(path, "season-lineup", f"""    <div class="s1-coming-head reveal">
      <div class="s1-label">The Lineup</div>
      <h2>The Full <em>Season.</em></h2>
      <div class="s1-coming-meta">
        <span>{count}</span><i></i>
        {middle}<i></i>
        <span>New Episodes Bi-Weekly</span>
      </div>
    </div>
    <div class="s1-coming-grid">
{chr(10).join(cards)}
    </div>""")


def series_page(data):
    """/series/: the one status line under the Season One feature."""
    eps = of_show(data, "series", 1)
    live = any(e["live"] for e in eps)
    status = "<span><b>Now Streaming</b></span>" if live else f"<span>Premieres <b>{when(eps[0])}</b></span>"
    region("series/index.html", "series-meta", f"""        <div class="sr-meta">
          <span>{len(eps)} Episodes</span><i></i>
          {status}<i></i>
          <span>Bi-Weekly</span>
        </div>""")


def context_page(data):
    """/context/: the newest episode as the feature, then what is next."""
    newest = latest_live(data, "context")
    nxt = [e for e in data["upcoming"] if e["show"] == "context"][:3]
    if not newest:
        return
    eyebrow = "The First Correction" if newest["number"] == 1 else "Latest Episode"
    rows = "\n".join(f"""        <li class="cm-row">
          <span class="cm-row-num" aria-hidden="true">{two(e['number'])}</span>
          <div>
            <h3 class="cm-row-title">{esc(e['title'])}</h3>
            <p class="cm-row-verse">{('"' + esc(e['quote']) + '" · ') if e.get('quote') else ''}{esc(e['scripture'])}</p>
          </div>
          <span class="cm-row-status">{when(e)}</span>
        </li>""" for e in nxt)
    up_next = f"""
    <div class="cm-next reveal">
      <div class="eyebrow">
        <div class="eyebrow-line"></div>
        <span class="eyebrow-text">Up Next</span>
      </div>
      <ul class="cm-list">
{rows}
      </ul>
    </div>""" if nxt else ""
    region("context/index.html", "context-episodes", f"""    <div class="coming-bg-text" aria-hidden="true">{two(newest['number'])}</div>
    <div class="coming-grid">
      <a class="ep-thumb reveal" href="{newest['path']}" aria-label="Watch Episode {newest['number']}: {esc(newest['title'])}">
        <img src="{esc(newest['image'])}" alt="" loading="lazy" />
        <span class="ep-thumb-time"><svg width="11" height="11" viewBox="0 0 24 24" fill="#D4A840" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>{esc(newest['runtime'])}</span>
      </a>
      <div class="coming-inner reveal reveal-delay-2">
        <div class="eyebrow">
          <div class="eyebrow-line"></div>
          <span class="eyebrow-text">{eyebrow}</span>
        </div>
        <div class="coming-kicker">Context Matters · Episode {two(newest['number'])} · Now Streaming</div>
        <h2 class="coming-title">{emphasize(newest)}</h2>
        <div class="coming-verse">{verse(newest)}</div>
        <p class="coming-desc">{esc(newest['hook'])}</p>
        <a class="coming-cta" href="{newest['path']}">Watch Episode {newest['number']}</a>
      </div>
    </div>{up_next}""")


# ---------------------------------------------------------------- sitemap

def build_sitemap(data):
    rows = [f"  <url><loc>{data['site']}{p}</loc></url>" for p in STATIC_PAGES]
    rows += [f"  <url><loc>{data['site']}{e['path']}</loc><lastmod>{e['air'].date().isoformat()}</lastmod></url>" for e in data["live"]]
    body = "\n".join(rows)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {data['site']}/sitemap.xml\n")


# ---------------------------------------------------------------- run

CHANGED = []


def write(path, content):
    file = ROOT / path
    file.parent.mkdir(parents=True, exist_ok=True)
    if not file.exists() or file.read_text(encoding="utf-8") != content:
        file.write_text(content, encoding="utf-8")
        CHANGED.append(path)


def main():
    data = load()
    build_watch(data)
    for ep in data["live"]:
        build_episode(data, ep)
    home_series(data)
    home_context(data)
    season_page(data, "series", 1, "season1/index.html")
    series_page(data)
    context_page(data)
    build_sitemap(data)

    print(f"{len(data['live'])} live, {len(data['upcoming'])} upcoming.")
    for ep in data["live"]:
        print(f"  live      {ep['path']:<34} {ep['title']}")
    for ep in data["upcoming"]:
        print(f"  upcoming  {day_short(ep['air'].date()):<34} {ep['show_name']}, {ep['label']}: {ep['title']}")
    print(("Updated:\n  " + "\n  ".join(CHANGED)) if CHANGED else "Nothing changed. Everything was already up to date.")


if __name__ == "__main__":
    main()
