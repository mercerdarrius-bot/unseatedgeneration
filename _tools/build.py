#!/usr/bin/env python3
"""Build every episode surface on unseatedgen.org from one list.

    python3 _tools/build.py

Reads   _tools/episodes.json   (the only file you edit to add an episode)
Writes  /watch/index.html                     the catalog: every episode, by show
        /<show>/.../episode-N/index.html       one page per live episode (for sharing)
        the marked regions inside index.html
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
DOWN = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" '
        'aria-hidden="true"><path d="M12 5v14M5 12l7 7 7-7"/></svg>')

# Merx Analytics, in the head of every built page right after the metas. The hand-built
# pages carry the same tags. Plain tags on purpose: the daily tag check reads the served HTML.
ANALYTICS = """  <!-- Merx Analytics: cookieless and first party (see the privacy page). Plain tags on purpose:
       the daily tag check reads the served HTML. -->
  <script>window.mx=window.mx||function(){(window.mx.q=window.mx.q||[]).push(arguments)}</script>
  <script defer src="https://a.merxstudios.com/m.js" data-site="qnutkrkhywct3hyx"></script>"""

# Hand-built pages that belong in the sitemap. Episode pages and /watch/ are added by the build.
STATIC_PAGES = ["/", "/watch/", "/mission/", "/about/", "/get-involved/"]


# ---------------------------------------------------------------- helpers

def esc(text):
    return html.escape(str(text), quote=True)


def two(n):
    return f"{n:02d}"


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
    for key, show in data["shows"].items():
        show["key"] = key
        show["home"] = "/watch/#" + show["anchor"]

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
        ep["key"] = "-".join(str(x) for x in (ep["show"], ep.get("season"), ep["number"]) if x)

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
{ANALYTICS}
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


def nav(active=None):
    """Main nav. `active` is the href to mark; aria-current only when it is this very page."""
    items = [("/watch/", "Watch"), ("/mission", "The Mission"), ("/about", "About"), ("/get-involved/", "Get Involved")]
    rows = []
    for href, label in items:
        mark = ""
        if href == active:
            mark = ' class="active"' + (' aria-current="page"' if active == "/watch/" and CURRENT == "/watch/" else "")
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
          <li><a href="/watch/#unseated-series">The Unseated Series</a></li>
          <li><a href="/watch/#context-matters">Context Matters</a></li>
        </ul>
      </div>
      <div>
        <div class="footer-col-head">Platform</div>
        <ul class="footer-links">
          <li><a href="/mission">The Mission</a></li>
          <li><a href="/about">About</a></li>
          <li><a href="/get-involved/">Get Involved</a></li>
          <li><a href="/privacy/">Privacy</a></li>
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

def player_data(data):
    """What the on-page player needs for every live episode and trailer, as a
    JSON script tag. assets/episodes.js reads it; [data-episode] keys point into it."""
    items = []
    for key in data["shows"]:
        eps = of_show(data, key)
        for i, ep in enumerate(eps):
            if not ep["live"]:
                continue
            later = next((e for e in eps[i + 1:] if e["live"]), None)
            items.append({
                "key": ep["key"], "youtube": ep["youtube"], "title": ep["title"],
                "kicker": f'{ep["show_name"]} · {ep["label"]}',
                "meta": f'{ep["scripture"]} · {ep["translation"]} · {runtime_minutes(ep["runtime"])} min · {day_medium(ep["air"].date())}',
                "hook": ep["hook"], "page": ep["path"], "next": later["key"] if later else None,
            })
    for skey, season in data["seasons"].items():
        trailer = season.get("trailer")
        if not trailer:
            continue
        show_key, number = skey.rsplit("-", 1)
        show = data["shows"][show_key]
        items.append({
            "key": f"trailer-{skey}", "video": trailer["video"], "poster": trailer.get("poster"), "vertical": True,
            "title": f"Season {number} Trailer", "kicker": f'{show["name"]} · Season {number}: {season["title"]}',
            "meta": show.get("tagline"),
        })
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/json" id="ugEpisodes">{payload}</script>'


def runtime_chip(ep):
    return (f'<span class="c-time">{PLAY.format(10)}<span class="sr-only">Runtime </span>{esc(ep["runtime"])}</span>')


def tile(ep, level):
    """One episode in the catalog. Live: plays in one press. Upcoming: holds its place with a date."""
    h = f"h{level}"
    if ep["live"]:
        return f"""        <li class="c-tile">
          <a class="c-card" href="{ep['path']}" data-episode="{ep['key']}">
            <span class="c-thumb">
              <img src="{esc(ep['image'])}" alt="" width="1280" height="720" loading="lazy" />
              <span class="c-play" aria-hidden="true">{PLAY.format(22)}</span>
              {runtime_chip(ep)}
            </span>
            <span class="c-num">Episode {ep['number']}</span>
            <{h} class="c-title">{esc(ep['title'])}</{h}>
            <span class="c-meta">{esc(ep['scripture'])} · {when(ep)}</span>
          </a>
        </li>"""
    tone = f"tone-{(ep['number'] - 1) % 4 + 1}" if ep["show"] == "series" else "tone-cm"
    return f"""        <li class="c-tile is-soon">
          <div class="c-card">
            <span class="c-thumb {tone}">
              <span class="c-soon-num" aria-hidden="true">{two(ep['number'])}</span>
              <span class="c-soon-date">Premieres {when(ep)}</span>
            </span>
            <span class="c-num">Episode {ep['number']} · Upcoming</span>
            <{h} class="c-title">{esc(ep['title'])}</{h}>
            <span class="c-meta">{verse(ep)}</span>
          </div>
        </li>"""


def show_section(data, key, raised):
    """Every episode of one show, grouped by season, in order."""
    show = data["shows"][key]
    eps = of_show(data, key)
    live = [e for e in eps if e["live"]]
    upcoming = [e for e in eps if not e["live"]]
    heading = esc(show["name"])
    if show.get("emphasis") and esc(show["emphasis"]) in heading:
        heading = heading.replace(esc(show["emphasis"]), f"<em>{esc(show['emphasis'])}.</em>", 1)
    nxt = f'<span>Next Episode <b>{when(upcoming[0])}</b></span>' if upcoming else "<span>All Episodes Streaming</span>"
    title_id = show["anchor"] + "-title"

    seasons = sorted({e.get("season") for e in eps}, key=lambda n: n or 0)
    trailer = ""
    blocks = []
    for number in seasons:
        group = [e for e in eps if e.get("season") == number]
        if number:
            info = data["seasons"][f"{key}-{number}"]
            name = esc(info["title"])
            if info.get("emphasis") and esc(info["emphasis"]) in name:
                name = name.replace(esc(info["emphasis"]), f"<em>{esc(info['emphasis'])}</em>", 1)
            if info.get("trailer") and not trailer:
                trailer = (f'<a class="btn btn-ghost reveal reveal-2" href="{info["trailer"]["video"]}" data-episode="trailer-{key}-{number}">'
                           f'{PLAY.format(12)} Watch the Season {number} Trailer</a>')
            soon = [e for e in group if not e["live"]]
            count = f'{len(group)} Episodes' + (f' · {len(group) - len(soon)} Streaming' if soon else '')
            blocks.append(f"""      <div class="c-season reveal">
        <h3 class="c-season-title">Season {number}: {name}</h3>
        <p class="meta"><span>{count}</span></p>
      </div>
      <ul class="c-grid">
{chr(10).join(tile(e, 4) for e in group)}
      </ul>""")
        else:
            blocks.append(f"""      <ul class="c-grid">
{chr(10).join(tile(e, 3) for e in group)}
      </ul>""")

    return f"""
    <section class="c-show{' c-show-raised' if raised else ''}" id="{show['anchor']}" aria-labelledby="{title_id}">
      <div class="c-wrap">
      <header class="c-show-head">
        <div class="reveal">
          <div class="eyebrow"><span>{esc(show['tagline'])}</span></div>
          <h2 class="h2" id="{title_id}">{heading}</h2>
          <p class="c-show-desc">{esc(show['about'])}</p>
          <p class="meta"><span>{len(live)} Streaming</span><i></i>{nxt}<i></i><span>New Episodes Bi-Weekly</span></p>
        </div>
        {trailer}
      </header>
{chr(10).join(blocks)}
      </div>
    </section>
"""


def build_watch(data):
    """/watch/: the catalog. Latest episode up top, then every show with every episode."""
    live, upcoming = data["live"], data["upcoming"]
    newest = live[0] if live else None
    desc = ("Every episode of The Unseated Series and Context Matters in one place. "
            "New teaching premieres Tuesdays at 6 PM ET.")
    image = newest["image_abs"] if newest else data["site"] + "/Photos/S1E1-Thumbnail.jpg"
    extra = f'\n  <link rel="stylesheet" href="{asset("/assets/player.css")}" />'

    global CURRENT
    CURRENT = "/watch/"
    out = [head(data, "Watch · Unseated Generation", desc, "/watch/", image, extra=extra), nav("/watch/")]
    CURRENT = None

    jumps = []
    for key, show in data["shows"].items():
        count = sum(1 for e in live if e["show"] == key)
        jumps.append(f'<li><a href="#{show["anchor"]}">{esc(show["name"])} '
                     f'<span>{count} {"Episode" if count == 1 else "Episodes"} {DOWN}</span></a></li>')
    next_line = ""
    if upcoming:
        u = upcoming[0]
        next_line = f'<p class="c-next fade">Next premiere: <b>{esc(u["show_name"])}, Episode {u["number"]}</b> · {when(u)} at 6 PM ET</p>'

    feature = ""
    if newest:
        feature = f"""
        <div class="c-latest reveal reveal-2">
          <a class="c-feature" href="{newest['path']}" data-episode="{newest['key']}">
            <span class="c-thumb">
              <img src="{esc(newest['image'])}" alt="" width="1280" height="720" fetchpriority="high" />
              <span class="c-play" aria-hidden="true">{PLAY.format(30)}</span>
              {runtime_chip(newest)}
            </span>
            <span class="c-feature-body">
              <span class="c-label"><b>Latest Episode</b> · {esc(newest['show_name'])} · {newest['label']}</span>
              <h2 class="c-feature-title">{emphasize(newest)}</h2>
              <span class="c-meta">{verse(newest)} · {runtime_minutes(newest['runtime'])} min · {when(newest)}</span>
            </span>
          </a>
        </div>"""

    out.append(f"""  <main id="main">
    <section class="page-hero c-top">
      <div class="page-hero-bg"></div>
      <div class="c-top-inner">
        <div class="eyebrow"><span>Watch</span></div>
        <h1 class="page-title">
          <span class="word"><span class="word-inner">Every</span></span> <span class="word"><span class="word-inner">Episode.</span></span>
          <span class="word"><span class="word-inner">One</span></span> <span class="word"><span class="word-inner gold-shimmer">Place.</span></span>
        </h1>
        <div class="c-row">
          <div class="c-intro">
            <p class="page-desc fade">The Unseated Series and Context Matters, together. Press any episode to watch it right here.</p>
            {next_line}
            <nav class="c-jump fade" aria-label="Jump to a series">
              <ul>
                {(chr(10) + '                ').join(jumps)}
              </ul>
            </nav>
          </div>{feature}
        </div>
      </div>
    </section>
""")
    for i, key in enumerate(data["shows"]):
        out.append(show_section(data, key, raised=i > 0))
    out.append(f"""  </main>

  {player_data(data)}

""")
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

    crumbs = [f'<li><a href="/watch/">Watch</a></li>', f'<li><a href="{show["home"]}">{esc(show["name"])}</a></li>',
              f'<li aria-current="page">{ep["label"]}</li>']

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
            nav("/watch/")]
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
        out.append(f"""    <a href="{ep['path']}" class="ep-feature reveal" data-episode="{ep['key']}">
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
            cards.append(f'        <a class="ctx-card" href="{e["path"]}" data-episode="{e["key"]}">\n{inner}\n          <div class="ctx-arrow" aria-hidden="true">→</div>\n        </a>')
        else:
            cards.append(f'        <div class="ctx-card">\n{inner}\n        </div>')
    region("index.html", "home-context", "\n".join(cards))


def home_data(data):
    """Homepage: the player's stylesheet, the details it needs, and its script, so
    episode cards play in place. Asset links carry a content hash so a returning
    visitor never pairs new markup with an old cached script."""
    region("index.html", "home-head", f'  <link rel="stylesheet" href="{asset("/assets/player.css")}" />')
    region("index.html", "home-data", f'  {player_data(data)}\n  <script src="{asset("/assets/episodes.js")}" defer></script>')


# ---------------------------------------------------------------- sitemap

def build_sitemap(data):
    rows = [f"  <url><loc>{data['site']}{p}</loc></url>" for p in STATIC_PAGES]
    rows += [f"  <url><loc>{data['site']}{e['path']}</loc><lastmod>{e['air'].date().isoformat()}</lastmod></url>" for e in data["live"]]
    body = "\n".join(rows)
    write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n')
    write("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {data['site']}/sitemap.xml\n")


# ---------------------------------------------------------------- run

CHANGED = []
CURRENT = None


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
    home_data(data)
    build_sitemap(data)

    print(f"{len(data['live'])} live, {len(data['upcoming'])} upcoming.")
    for ep in data["live"]:
        print(f"  live      {ep['path']:<34} {ep['title']}")
    for ep in data["upcoming"]:
        print(f"  upcoming  {day_short(ep['air'].date()):<34} {ep['show_name']}, {ep['label']}: {ep['title']}")
    print(("Updated:\n  " + "\n  ".join(CHANGED)) if CHANGED else "Nothing changed. Everything was already up to date.")


if __name__ == "__main__":
    main()
