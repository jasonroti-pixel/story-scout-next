#!/usr/bin/env python3
"""
Story Scout Next — RSS ingest pipeline.
feedparser + newspaper3k → enrich → mix-balanced, then MERGED into the
existing data/stories.json board (never overwritten: every story already
on the board survives, fresh stories are added only when new).

Daily target ~280 stories with a soft ~12 Canadian-lane pack and a large
Arcade-style non-CA talk-radio mix (THE LIST, ENTERTAINMENT, TECH, etc.).
Cost driver is Actions minutes, not LLM tokens.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
import yaml

from enrich import StoryDeduper, enrich_story, make_story_id

ROOT = Path(__file__).resolve().parent.parent
FEEDS_PATH = Path(__file__).resolve().parent / "feeds.yml"
OUT_PATH = ROOT / "data" / "stories.json"
TZ = ZoneInfo("America/Toronto")

CANADIAN_SOURCE_HINTS = (
    "cbc",
    "ctv",
    "globe",
    "cp24",
    "toronto star",
    "r/canada",
    "reddit r/canada",
)

TALKABLE_CATEGORIES = {
    "THE LIST",
    "ENTERTAINMENT",
    "BREAKOUT WATCH",
    "LIFESTYLE CHAT",
    "TECH",
    "SPORTS",
    "CLOSER",
}


def load_config() -> dict[str, Any]:
    with FEEDS_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def slot_for_now(now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    # Morning prep vs evening prep
    return "am" if now.hour < 15 else "pm"


def parse_published(entry: dict[str, Any]) -> str:
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat()
        except Exception:
            pass
    for key in ("published_parsed", "updated_parsed"):
        struct = entry.get(key)
        if not struct:
            continue
        try:
            dt = datetime(*struct[:6], tzinfo=timezone.utc)
            return dt.isoformat()
        except Exception:
            pass
    return datetime.now(timezone.utc).isoformat()


def extract_body(url: str, fallback: str = "") -> str:
    """Try newspaper3k full text; fall back to feed summary."""
    if not url:
        return fallback
    try:
        from newspaper import Article
        article = Article(url)
        article.download()
        article.parse()
        text = (article.text or "").strip()
        if len(text) > 80:
            return text
    except Exception:
        pass
    return fallback


def clean_html_summary(raw: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", raw or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_feed_entries(feed_cfg: dict[str, Any], limit: int = 18) -> list[dict[str, Any]]:
    url = feed_cfg["url"]
    name = feed_cfg.get("name") or url
    category_hint = feed_cfg.get("category_hint")
    source_type = feed_cfg.get("source_type") or "news"

    parsed = feedparser.parse(url)
    entries: list[dict[str, Any]] = []
    for entry in (parsed.entries or [])[:limit]:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or "").strip()
        if not title or not link:
            continue
        summary = clean_html_summary(
            entry.get("summary") or entry.get("description") or ""
        )
        entries.append(
            {
                "title": title,
                "url": link,
                "summary": summary,
                "source": name,
                "source_type": source_type,
                "category_hint": category_hint,
                "source_published_at": parse_published(entry),
            }
        )
    return entries


def is_canadian_lane(story: dict[str, Any]) -> bool:
    entities = story.get("entities") or {}
    if entities.get("is_canadian"):
        return True
    if story.get("category") == "CANADIAN NEWS":
        return True
    source = (story.get("source") or "").lower()
    return any(hint in source for hint in CANADIAN_SOURCE_HINTS)


def balance_mix(
    stories: list[dict[str, Any]],
    max_stories: int,
    target_canadian: int,
) -> list[dict[str, Any]]:
    """Keep ~target_canadian CA-lane stories, fill the rest with non-CA talkables.

    High-scoring Canadian pieces may exceed the soft target only when non-CA
    inventory cannot fill remaining slots — never crowd out talkables when
    non-Canadian inventory exists.
    """
    ranked = sorted(stories, key=lambda s: float(s.get("score") or 0), reverse=True)
    ca = [s for s in ranked if is_canadian_lane(s)]
    non_ca = [s for s in ranked if not is_canadian_lane(s)]

    talkables = [s for s in non_ca if s.get("category") in TALKABLE_CATEGORIES]
    other_non = [s for s in non_ca if s.get("category") not in TALKABLE_CATEGORIES]
    non_ca_ordered = talkables + other_non

    selected: list[dict[str, Any]] = []
    used: set[str] = set()

    for s in ca[: max(0, target_canadian)]:
        selected.append(s)
        used.add(s["id"])

    for s in non_ca_ordered:
        if len(selected) >= max_stories:
            break
        if s["id"] in used:
            continue
        selected.append(s)
        used.add(s["id"])

    # Only add extra Canadian stories into leftover slots (no non-CA crowding).
    if len(selected) < max_stories:
        for s in ca[target_canadian:]:
            if len(selected) >= max_stories:
                break
            if s["id"] in used:
                continue
            selected.append(s)
            used.add(s["id"])

    selected.sort(key=lambda s: float(s.get("score") or 0), reverse=True)
    return selected[:max_stories]


def load_existing_board() -> list[dict[str, Any]]:
    """Load the stories already on the board, or [] when none exists yet."""
    if not OUT_PATH.is_file():
        return []
    try:
        payload = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[ingest] warn: could not read existing board: {exc}", flush=True)
        return []
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = payload.get("stories") or []
    else:
        return []
    return [s for s in raw if isinstance(s, dict)]


def merge_into_board(
    existing: list[dict[str, Any]],
    fresh: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Append fresh stories not already on the board. Never removes anything.

    Dedupe is by story id (SHA-256 prefix of URL/title), which is stable
    across runs, so a rerun adds nothing twice.
    """
    seen: set[str] = set()
    for story in existing:
        sid = story.get("id") or make_story_id(
            story.get("url") or "", story.get("title") or ""
        )
        story["id"] = sid
        seen.add(sid)

    merged = list(existing)
    added = 0
    for story in fresh:
        sid = story.get("id") or make_story_id(
            story.get("url") or "", story.get("title") or ""
        )
        story["id"] = sid
        if sid in seen:
            continue
        seen.add(sid)
        merged.append(story)
        added += 1
    return merged, added


def run(max_stories: int | None = None, fetch_full: bool = True) -> Path:
    cfg = load_config()
    pipeline_cfg = cfg.get("pipeline") or {}
    max_stories = max_stories or int(pipeline_cfg.get("max_stories") or 280)
    per_feed_limit = int(pipeline_cfg.get("per_feed_limit") or 18)
    target_canadian = int(pipeline_cfg.get("target_canadian") or 12)
    pipeline_version = str(pipeline_cfg.get("pipeline_version") or "1.1.0")
    now = datetime.now(TZ)
    date = now.date().isoformat()
    slot = slot_for_now(now)

    raw_items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for feed_cfg in cfg.get("feeds") or []:
        try:
            entries = fetch_feed_entries(feed_cfg, limit=per_feed_limit)
            print(f"[ingest] {feed_cfg.get('name')}: {len(entries)} entries", flush=True)
        except Exception as exc:
            print(f"[ingest] FAILED {feed_cfg.get('name')}: {exc}", flush=True)
            continue
        for entry in entries:
            url = entry["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            body = entry.get("summary") or ""
            if fetch_full:
                body = extract_body(url, fallback=body) or body
            raw_items.append(
                {
                    "id": make_story_id(url, entry["title"]),
                    "title": entry["title"],
                    "url": url,
                    "body": body,
                    "summary": entry.get("summary") or "",
                    "source": entry["source"],
                    "source_type": entry["source_type"],
                    "category_hint": entry.get("category_hint"),
                    "source_published_at": entry.get("source_published_at"),
                    "date": date,
                    "slot": slot,
                    "clips": [],
                }
            )

    deduper = StoryDeduper()
    stories: list[dict[str, Any]] = []
    for raw in raw_items:
        try:
            story = enrich_story(raw, deduper=deduper, pipeline_version=pipeline_version)
            stories.append(story)
        except Exception as exc:
            print(f"[enrich] skip {raw.get('title')}: {exc}", flush=True)

    # Prefer higher scores, then mix-balance BEFORE slicing to max_stories
    stories.sort(key=lambda s: float(s.get("score") or 0), reverse=True)
    stories = balance_mix(stories, max_stories=max_stories, target_canadian=target_canadian)

    for story in stories:
        story["related_count"] = deduper.related_count(story["cluster_id"])

    # Merge into the existing board instead of overwriting it: everything
    # already on the board survives (including merged Twitter packs); fresh
    # stories join only when their id is not already present.
    existing = load_existing_board()
    merged, added = merge_into_board(existing, stories)
    print(
        f"[ingest] board: {len(existing)} existing + {added} new = {len(merged)}",
        flush=True,
    )

    # Primary show pack ≈ Arcade morning size, re-ranked across the merged board
    primary_n = min(66, int(max_stories * 0.35))
    merged.sort(key=lambda s: float(s.get("score") or 0), reverse=True)
    for i, story in enumerate(merged):
        story["is_backup"] = i >= primary_n

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone": "America/Toronto",
        "date": date,
        "slot": slot,
        "pipeline_version": pipeline_version,
        "count": len(merged),
        "stories": merged,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ingest] wrote {len(merged)} stories ({added} new) → {OUT_PATH}", flush=True)
    return OUT_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Story Scout Next ingest")
    parser.add_argument("--max", type=int, default=None, help="Max stories to keep")
    parser.add_argument(
        "--no-fulltext",
        action="store_true",
        help="Skip newspaper3k full-text fetch (faster / CI-friendly)",
    )
    args = parser.parse_args(argv)
    try:
        run(max_stories=args.max, fetch_full=not args.no_fulltext)
    except Exception as exc:
        print(f"[ingest] fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
