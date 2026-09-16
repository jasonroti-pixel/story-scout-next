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
index.html
css/style.css
js/app.js search.js storage.js loadout.js clips.js
data/stories.json
pipeline/ingest.py enrich.py merge_twitter.py requirements.txt feeds.yml
data/twitter_stories.json (optional) data/incoming/*.json
.github/workflows/ingest.yml deploy.yml merge-twitter.yml
sw.js manifest.webmanifest
README.md CLAUDE.md
```

## Categories

THE LIST | ENTERTAINMENT | BREAKOUT WATCH | LIFESTYLE CHAT | CANADIAN NEWS | TECH | SPORTS | CLOSER

## Brands / themes

`data-theme="night|day"` and `data-brand="daily-goods|jaystation"` on `<html>`.

## Working tips

- After pipeline edits: `python3 -m py_compile pipeline/*.py`
- Local UI: `python3 -m http.server` from repo root
- Optional merge file: `data/twitter_stories.json` (same schema / `{stories:[…]}` envelope)
- Merge packs: `python merge_twitter.py` (URL/title match → append unique clips; else net-new)
- Manual Action: `merge-twitter.yml` (workflow_dispatch; not scheduled)
- Ingest crons target America/Toronto AM/PM prep windows via dual UTC schedules (EDT+EST)
