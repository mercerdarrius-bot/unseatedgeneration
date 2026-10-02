# Episodes

Every place an episode appears on unseatedgen.org is built from one file: `episodes.json`.

## When a new episode goes live

1. Open `_tools/episodes.json` and find the episode (it is already listed as upcoming).
2. Add three things to it:
   - `"youtube"`: the video id, the part after `watch?v=` in the YouTube link
   - `"runtime"`: the length, like `"26:44"`
   - `"hook"` and `"summary"`: one line, then two or three short paragraphs
3. Run the build from the site folder:

   ```bash
   python3 _tools/build.py
   ```

4. Commit and push. The site updates in about a minute.

That one change updates the homepage, the show page, the season page, the archive at `/watch/`, the sitemap, and creates the episode's own page.

## Fields

| Field | Needed | Notes |
| --- | --- | --- |
| `show` | always | `series` or `context` |
| `season` | Unseated Series only | a number |
| `number` | always | episode number within the season or show |
| `title` | always | the site title, which can differ from the YouTube title |
| `emphasis` | optional | one word of the title to set in gold italics |
| `scripture`, `translation` | always | e.g. `Acts 8:9–11`, `NASB` |
| `quote` | optional | the phrase being examined (Context Matters) |
| `date` | always | air date, `2026-10-06` |
| `youtube` | when live | the episode is "live" once this is filled in |
| `runtime` | when live | `26:44` |
| `hook` | when live | one sentence, shown on cards and in link previews |
| `summary` | when live | list of short paragraphs for the episode page |
| `thumb` | optional | a file in `/Photos`. Without it, the YouTube thumbnail is used |

## Good to know

- An episode with no `youtube` id shows as upcoming with its date. If that date passes before the site is rebuilt, visitors see "Coming Soon" instead of a stale date.
- To add a brand new episode or season, copy an existing entry. A new season also needs a line under `"seasons"`.
- The build refuses to run if something is missing or if any text contains an em dash, and tells you what to fix.
- `/watch/`, the episode pages, `sitemap.xml`, and `robots.txt` are written by the build. Do not edit them by hand. On the other pages, only the parts between `<!-- BUILD:... -->` markers are rewritten.
- Shared look and behavior for the generated pages live in `/assets/episodes.css`, `/assets/episodes.js`, and `/assets/chrome.js`.
