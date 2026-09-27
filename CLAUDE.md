# CLAUDE.md — Story Scout Next

## What this is

Brand-new static radio-prep app: **GitHub Pages SPA** + **Python ingest/enrich Actions pipeline**.  
Clips are URL metadata only — never commit media binaries.

## Hard rules

- Do **not** add a backend, npm build step, PocketBase, auth, Yjs, ffmpeg, TTS, teleprompter, or Twitter scraping.
- Do **not** store clip media in the repo; `clips[]` is link-out only.
- Keep CDN-only frontend: Dexie, Orama, SortableJS, NES.css + Google Fonts.
- Pipeline stack: feedparser, newspaper3k, spaCy NER, vaderSentiment, sumy LexRank, datasketch MinHash LSH.
- Cap ~80 stories in `data/stories.json`; ids are SHA-256 prefixes of URL/title.

## Layout

```
index.html                     root version picker (links to v1/ and v2/)
v1/                            ORIGINAL arcade app — FROZEN, never edit
  index.html css/style.css js/{app,search,storage,loadout,clips}.js
  sw.js manifest.webmanifest assets/
v2/                            "Peak Arcade" rebuild — operational clone of v1
  index.html css/style.css css/scenes.css
  js/{app,search,storage,loadout,clips}.js   same logic as v1
  js/arcade.js                 visual only: scenes, hidden Nicos, end credits
  assets/px/*.svg              generated pixel art (Nico sprites, scenes)
  assets/daily-goods-logo.jpeg
  tools/pixelart.py palette.py nico.py  generator (stdlib; re-run to redraw art;
                               nico.py = detailed Nico master + derived sprites)
  PALETTE.md                   expanded palette + usage rules
  sw.js manifest.webmanifest
data/stories.json              shared by v1 and v2 (fetched as ../data/…)
data/twitter_stories.json (optional) data/incoming/*.json
pipeline/ingest.py enrich.py merge_twitter.py requirements.txt feeds.yml
.github/workflows/ingest.yml deploy.yml merge-twitter.yml
README.md CLAUDE.md
```

### v1 / v2 rules

- **v1 is frozen.** Do not modify anything under `v1/`.
- **v2 must stay an operational clone of v1.** It has the same features, data flow, filters and loadout options. Only visuals, palette and fonts differ. Keep JS logic changes in `v2/js/app.js` etc. in lockstep with v1 behaviour. New v2-only behaviour is presentation only and lives in `v2/js/arcade.js`.
- **Isolation.** v2 uses its own IndexedDB (`StoryScoutNextV2`) and service-worker caches (`ssn-v2-*`, and it deletes only its own old caches). v1 keeps `StoryScoutNext` and `story-scout-next-v6`. Each SW is scoped to its own folder.
- **v2 art.** Edit `v2/tools/pixelart.py`, run `python3 v2/tools/pixelart.py`, and commit the regenerated `v2/assets/px/*.svg`. This is not a build step: the SVGs are committed.
- **v2 palette.** Use only the tokens in `v2/PALETTE.md` (six owner colours plus derived ramps), and keep `tools/palette.py`, `css/style.css :root` and `PALETTE.md` in sync.

## Categories

THE LIST | ENTERTAINMENT | BREAKOUT WATCH | LIFESTYLE CHAT | CANADIAN NEWS | TECH | SPORTS | CLOSER

## Brands / themes

`data-theme="night|day"` and `data-brand="daily-goods|jaystation"` on `<html>`.

## Working tips

- After pipeline edits: `python3 -m py_compile pipeline/*.py`
- Local UI: `python3 -m http.server` from repo root, then open `/` (menu), `/v1/` or `/v2/`
- Optional merge file: `data/twitter_stories.json` (same schema / `{stories:[…]}` envelope)
- Merge packs: `python merge_twitter.py` (URL/title match → append unique clips; else net-new)
- Manual Action: `merge-twitter.yml` (workflow_dispatch; not scheduled)
- Ingest crons target America/Toronto AM/PM prep windows via dual UTC schedules (EDT+EST)
