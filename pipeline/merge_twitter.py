#!/usr/bin/env python3
"""
Story Scout Next — merge Twitter / social story packs into data/stories.json.

Incoming packs:
  - data/twitter_stories.json  (array or {stories:[...]})
  - data/incoming/*.json       (same shapes)

Match existing stories by normalized URL, else fuzzy title.
If match + clips: append unique clips by url (no duplicate stories).
If match + no clips: skip.
If no match: add as net-new (id, clips, source_type social/twitter).

Writes:
  - data/stories.json
  - data/last_merge_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORIES = ROOT / "data" / "stories.json"
DEFAULT_TWITTER = ROOT / "data" / "twitter_stories.json"
DEFAULT_INCOMING_DIR = ROOT / "data" / "incoming"
DEFAULT_REPORT = ROOT / "data" / "last_merge_report.json"

# High similarity for title fuzzy match (normalized alphanumeric).
TITLE_SIMILARITY_THRESHOLD = 0.88

CLIP_KEYS = (
    "type",
    "platform",
    "url",
    "thumbnail_url",
    "duration_seconds",
    "description",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_story_id(url: str, title: str = "") -> str:
    raw = (url or title or "").strip().lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    u = str(url).strip().lower()
    # Drop fragment / common tracking query noise for matching
    if "#" in u:
        u = u.split("#", 1)[0]
    if "?" in u:
        base, qs = u.split("?", 1)
        keep = []
        for part in qs.split("&"):
            key = part.split("=", 1)[0]
            if key.startswith("utm_") or key in ("fbclid", "gclid", "ref", "s"):
                continue
            if part:
                keep.append(part)
        u = base + (("?" + "&".join(keep)) if keep else "")
    u = re.sub(r"^https?://(www\.)?", "", u)
    u = u.rstrip("/")
    return u


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    return re.sub(r"[^a-z0-9]+", "", str(title).lower())


def title_similarity(a: str, b: str) -> float:
    na, nb = normalize_title(a), normalize_title(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_stories(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return [s for s in payload if isinstance(s, dict)]
    if isinstance(payload, dict):
        stories = payload.get("stories")
        if isinstance(stories, list):
            return [s for s in stories if isinstance(s, dict)]
    return []


def load_incoming(twitter_path: Path, incoming_dir: Path) -> list[dict[str, Any]]:
    """Load packs from twitter_stories.json and data/incoming/*.json."""
    collected: list[dict[str, Any]] = []
    sources: list[str] = []

    if twitter_path.is_file():
        try:
            collected.extend(extract_stories(load_json(twitter_path)))
            sources.append(str(twitter_path))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"[merge_twitter] warn: skip {twitter_path}: {exc}", file=sys.stderr)

    if incoming_dir.is_dir():
        for path in sorted(incoming_dir.glob("*.json")):
            try:
                collected.extend(extract_stories(load_json(path)))
                sources.append(str(path))
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[merge_twitter] warn: skip {path}: {exc}", file=sys.stderr)

    print(f"[merge_twitter] loaded {len(collected)} incoming story(ies) from {len(sources)} file(s)")
    return collected


def normalize_clip(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    url = (raw.get("url") or "").strip()
    if not url:
        return None
    clip: dict[str, Any] = {
        "type": raw.get("type") or "video",
        "platform": raw.get("platform") or "twitter",
        "url": url,
        "thumbnail_url": raw.get("thumbnail_url") or "",
        "duration_seconds": raw.get("duration_seconds"),
        "description": raw.get("description") or "",
    }
    # Preserve only known clip schema keys (+ keep duration None as None)
    return {k: clip.get(k) for k in CLIP_KEYS}


def clip_urls(clips: list[dict[str, Any]]) -> set[str]:
    return {normalize_url(c.get("url")) for c in clips if c.get("url")}


def ensure_story_shape(story: dict[str, Any]) -> dict[str, Any]:
    """Ensure net-new / incoming stories have required fields."""
    out = dict(story)
    title = (out.get("title") or "").strip()
    url = (out.get("url") or "").strip()
    if not out.get("id"):
        out["id"] = make_story_id(url, title)
    clips_raw = out.get("clips") or []
    clips: list[dict[str, Any]] = []
    seen = set()
    for c in clips_raw:
        nc = normalize_clip(c)
        if not nc:
            continue
        key = normalize_url(nc["url"])
        if key in seen:
            continue
        seen.add(key)
        clips.append(nc)
    out["clips"] = clips

    st = (out.get("source_type") or "").strip().lower()
    if st not in ("social", "twitter"):
        out["source_type"] = "social"
    # Hint platform origin without inventing new top-level fields when already set
    if not out.get("source"):
        out["source"] = "Twitter / X"

    meta = dict(out.get("meta") or {})
    if "ingested_at" not in meta:
        meta["ingested_at"] = utc_now_iso()
    out["meta"] = meta

    # Sensible defaults for optional schema fields
    out.setdefault("date", datetime.now(timezone.utc).date().isoformat())
    out.setdefault("slot", "am")
    out.setdefault("category", "THE LIST")
    out.setdefault("angle", "")
    out.setdefault("bullets", [])
    out.setdefault("debate", "")
    out.setdefault("score", 50.0)
    out.setdefault("is_backup", False)
    out.setdefault(
        "entities",
        {"people": [], "organizations": [], "locations": [], "is_canadian": False},
    )
    out.setdefault("sentiment", {"compound": 0.0, "label": "neutral"})
    out.setdefault("summary", "")
    out.setdefault("cluster_id", out["id"])
    out.setdefault("related_count", 0)
    return out


def find_match(
    incoming: dict[str, Any],
    stories: list[dict[str, Any]],
    url_index: dict[str, int],
) -> int | None:
    """Return index of matching existing story, or None."""
    nurl = normalize_url(incoming.get("url"))
    if nurl and nurl in url_index:
        return url_index[nurl]

    title = incoming.get("title") or ""
    if not normalize_title(title):
        return None

    best_idx: int | None = None
    best_score = 0.0
    for i, existing in enumerate(stories):
        score = title_similarity(title, existing.get("title") or "")
        if score >= TITLE_SIMILARITY_THRESHOLD and score > best_score:
            best_score = score
            best_idx = i
    return best_idx


def append_unique_clips(
    existing: dict[str, Any],
    incoming_clips: list[dict[str, Any]],
) -> int:
    """Append unique clips by normalized url. Returns count newly attached."""
    existing.setdefault("clips", [])
    if not isinstance(existing["clips"], list):
        existing["clips"] = []
    seen = clip_urls(existing["clips"])
    attached = 0
    for raw in incoming_clips:
        clip = normalize_clip(raw)
        if not clip:
            continue
        key = normalize_url(clip["url"])
        if key in seen:
            continue
        existing["clips"].append(clip)
        seen.add(key)
        attached += 1

    if attached:
        # source_type hint + meta timestamp
        st = (existing.get("source_type") or "").strip().lower()
        if not st:
            existing["source_type"] = "social"
        meta = dict(existing.get("meta") or {})
        meta["clip_attached_at"] = utc_now_iso()
        existing["meta"] = meta
    return attached


def merge(
    stories_payload: dict[str, Any],
    incoming: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    stories = list(stories_payload.get("stories") or [])
    url_index: dict[str, int] = {}
    for i, s in enumerate(stories):
        nurl = normalize_url(s.get("url"))
        if nurl and nurl not in url_index:
            url_index[nurl] = i

    report: dict[str, Any] = {
        "merged_at": utc_now_iso(),
        "attached_clips": 0,
        "added": 0,
        "skipped": 0,
        "details": {
            "attached": [],
            "added": [],
            "skipped": [],
        },
    }

    for raw in incoming:
        if not isinstance(raw, dict):
            continue
        inc = ensure_story_shape(raw)
        clips = list(inc.get("clips") or [])
        match_idx = find_match(inc, stories, url_index)

        if match_idx is not None:
            if clips:
                n = append_unique_clips(stories[match_idx], clips)
                if n:
                    report["attached_clips"] += n
                    report["details"]["attached"].append(
                        {
                            "id": stories[match_idx].get("id"),
                            "title": stories[match_idx].get("title"),
                            "clips_added": n,
                        }
                    )
                else:
                    report["skipped"] += 1
                    report["details"]["skipped"].append(
                        {
                            "reason": "match_clips_already_present",
                            "id": stories[match_idx].get("id"),
                            "title": stories[match_idx].get("title"),
                        }
                    )
            else:
                report["skipped"] += 1
                report["details"]["skipped"].append(
                    {
                        "reason": "match_no_clips",
                        "id": stories[match_idx].get("id"),
                        "title": stories[match_idx].get("title"),
                    }
                )
            continue

        # Net-new
        stories.append(inc)
        nurl = normalize_url(inc.get("url"))
        if nurl and nurl not in url_index:
            url_index[nurl] = len(stories) - 1
        report["added"] += 1
        report["details"]["added"].append(
            {
                "id": inc.get("id"),
                "title": inc.get("title"),
                "clips": len(inc.get("clips") or []),
            }
        )

    out = dict(stories_payload)
    out["stories"] = stories
    out["count"] = len(stories)
    out["generated_at"] = utc_now_iso()
    return out, report


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge Twitter packs into stories.json")
    parser.add_argument("--stories", type=Path, default=DEFAULT_STORIES)
    parser.add_argument("--twitter", type=Path, default=DEFAULT_TWITTER)
    parser.add_argument("--incoming-dir", type=Path, default=DEFAULT_INCOMING_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute merge and report without writing stories.json",
    )
    args = parser.parse_args(argv)

    if not args.stories.is_file():
        print(f"[merge_twitter] error: stories file missing: {args.stories}", file=sys.stderr)
        return 1

    payload = load_json(args.stories)
    if isinstance(payload, list):
        payload = {"stories": payload, "count": len(payload)}
    if not isinstance(payload, dict):
        print("[merge_twitter] error: stories.json must be object or array", file=sys.stderr)
        return 1

    incoming = load_incoming(args.twitter, args.incoming_dir)
    if not incoming:
        report = {
            "merged_at": utc_now_iso(),
            "attached_clips": 0,
            "added": 0,
            "skipped": 0,
            "details": {"attached": [], "added": [], "skipped": []},
            "note": "no incoming packs found",
        }
        if not args.dry_run:
            write_json(args.report, report)
        print("[merge_twitter] nothing to merge")
        print(json.dumps(report, indent=2))
        return 0

    updated, report = merge(payload, incoming)

    if not args.dry_run:
        write_json(args.stories, updated)
        write_json(args.report, report)

    print(
        f"[merge_twitter] attached_clips={report['attached_clips']} "
        f"added={report['added']} skipped={report['skipped']}"
    )
    print(json.dumps({k: report[k] for k in ("attached_clips", "added", "skipped", "merged_at")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
