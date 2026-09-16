# Story Scout Next

Static **GitHub Pages SPA** + **Python Actions pipeline** for Canadian radio-prep storytelling.

No backend. No npm build — CDN JavaScript only (Dexie, Orama, SortableJS, NES.css).  
Clips are **link-out metadata only** (no media files in the repo).

## Quick start (local)

```bash
# Serve the static app (any static server)
cd story-scout-next
python3 -m http.server 8080
# open http://localhost:8080
```

## Pipeline

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
python ingest.py            # fulltext via newspaper3k
python ingest.py --no-fulltext   # faster / CI
```

Writes `data/stories.json` (capped ~280 stories, hashed ids).

**Daily output target:** ~280 stories with a soft ~12 Canadian-lane pack and a large non-CA Arcade-style talk-radio mix (US viral, entertainment, tech, lifestyle, sports, closers). Ingest cost is GitHub Actions minutes, not LLM tokens.

### Cron (GitHub Actions)

`ingest.yml` runs (UTC crons approximating America/Toronto):

- Mon–Fri **09:30** ET
- Mon–Fri **23:30** ET
- Sunday **23:30** ET  
(+ `workflow_dispatch`)

`deploy.yml` publishes to GitHub Pages on push to `main`.

## Story schema

`id`, `date`, `slot` (`am`|`pm`), `category`, `title`, `angle`, `bullets[]`, `debate`, `source`, `source_type`, `url`, `score`, `is_backup`, `entities{people,organizations,locations,is_canadian}`, `sentiment{compound,label}`, `summary`, `cluster_id`, `related_count`, `clips[{type,platform,url,thumbnail_url,duration_seconds,description}]`, `meta{ingested_at,source_published_at,pipeline_version}`

### Categories

`THE LIST` · `ENTERTAINMENT` · `BREAKOUT WATCH` · `LIFESTYLE CHAT` · `CANADIAN NEWS` · `TECH` · `SPORTS` · `CLOSER`

## Frontend features

- Loads `data/stories.json` (+ optional `data/twitter_stories.json` merge)
- Dexie IndexedDB cache + Orama search
- Filters / sorts, story cards, detail view
- Sortable loadout with notes, backup flag, save/load, prep sheet
- Custom stories
- Clip link-outs
- Night/Day theme + Daily Goods / Jaystation brand
- PWA offline shell + last-updated status
- Mobile responsive retro arcade UI (Press Start 2P + Inter, NES.css)

## Intentionally out of scope

PocketBase, auth, Yjs, ffmpeg, TTS, teleprompter, Twitter scraping.

## License

Private / internal radio-prep tooling.
