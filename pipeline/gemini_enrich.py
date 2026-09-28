#!/usr/bin/env python3
"""Gemini writing pass for Story Scout Next ingest.

Replaces the template-generated angle / debate / bullets with real
producer-style copy written by Gemini in the show's voice.

Reads stories.json, enriches stories that don't yet carry the
meta.gemini_enrich flag, and writes the file back in place.

The Gemini API key comes from the GEMINI_API_KEY environment variable
(GitHub Actions: secrets.GEMINI_API_KEY). stdlib only.

Usage:
    GEMINI_API_KEY=... python3 pipeline/gemini_enrich.py [--input data/stories.json]
                                                        [--limit 40] [--force]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

MODEL = "gemini-3.8-flash"
ENRICH_FLAG = "gemini-v1"
API_URL = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"{MODEL}:generateContent")

PROMPT = """You are writing a radio show prep sheet for THE DAILY GOODS, a Canadian daily talk-radio show. Read the story below and write the three prep fields.

INPUT
Headline: {title}
Category: {category}
Article text:
\"\"\"
{text}
\"\"\"

OUTPUT: a single JSON object, nothing else, with exactly these keys:
{{
  "angle": "1-2 sentence on-air hook telling the host why the audience cares and what the talkable take is. Punchy, warm, concrete, written to be spoken aloud.",
  "bullets": ["7 to 9 bullets. Each bullet is one complete, information-dense sentence in neutral AP/wire style, third person, past tense. One distinct fact per bullet, never merge two facts. Keep every specific: full names, ages, exact dates, locations, dollar amounts, scores. Pull key quotes VERBATIM in quotation marks, at least two when the article contains them. Order: core news first, then background, context, reactions, quotes. Facts and quotes only."],
  "debate": "One caller-friendly debate question specific to THIS story, the kind that lights up the phone lines."
}}

RULES
- No em dashes anywhere. Use commas, colons, or parentheses instead.
- Never use "it's not X, it's Y" phrasing.
- No AI-sounding filler, no cliches, no "this highlights/shows/demonstrates" lines.
- Decode HTML entities into plain characters. Never leave codes like &#8217; in the text.
- Work in a Canadian angle where one fits naturally.
- Use only facts stated in the article. Do not invent anything.
- Output ONLY the JSON object."""


def clean(text: str) -> str:
    """Decode entities and strip feed truncation artifacts."""
    t = html.unescape(text or "")
    t = re.sub(r"\s*\[&#8230;?\]|\s*\[&hellip;\]|\s*\[\.\.\.\]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def gemini_write(api_key: str, title: str, category: str, text: str,
                 retries: int = 3) -> dict | None:
    prompt = PROMPT.format(title=clean(title), category=category or "",
                           text=clean(text)[:6000] or clean(title))
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048},
    }).encode("utf-8")
    last_error = None
    for attempt in range(retries):
        req = urllib.request.Request(
            API_URL, data=body, method="POST",
            headers={"Content-Type": "application/json",
                     "x-goog-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.load(resp)
            cand = (payload.get("candidates") or [{}])[0]
            parts = ((cand.get("content") or {}).get("parts")) or []
            raw = "".join(p.get("text", "") for p in parts).strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                raw = m.group(0)
            # tolerate control characters inside strings
            raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", raw)
            data = json.loads(raw, strict=False)
            angle = clean(str(data.get("angle", "")))
            bullets = [clean(str(b)) for b in (data.get("bullets") or [])
                       if str(b).strip()]
            debate = clean(str(data.get("debate", "")))
            if angle and bullets:
                return {"angle": angle, "bullets": bullets, "debate": debate}
            last_error = "empty fields in response"
        except Exception as e:  # noqa: BLE001
            last_error = str(e)[:200]
            time.sleep(2 * (attempt + 1))
    print(f"  WARN: Gemini failed for {title[:60]!r}: {last_error}",
          file=sys.stderr)
    return None


def story_text(s: dict) -> str:
    parts = [s.get("summary") or "", s.get("title") or ""]
    return "\n".join(p for p in parts if p)


def needs_enrichment(s: dict) -> bool:
    if s.get("_custom"):
        return False
    meta = s.get("meta") or {}
    return meta.get("gemini_enrich") != ENRICH_FLAG


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data/stories.json")
    ap.add_argument("--limit", type=int, default=60,
                    help="max stories to enrich per run")
    ap.add_argument("--force", action="store_true",
                    help="re-enrich even flagged stories")
    args = ap.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("GEMINI_API_KEY not set; skipping Gemini enrichment.")
        return 0

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    stories = data.get("stories", data if isinstance(data, list) else [])
    targets = [s for s in stories
               if (args.force or needs_enrichment(s)) and story_text(s)]
    print(f"enriching {min(len(targets), args.limit)} of {len(targets)} "
          f"pending stories")
    done = 0
    for s in targets[:args.limit]:
        result = gemini_write(api_key, s.get("title", ""),
                              s.get("category", ""), story_text(s))
        if result:
            # Clean the leftovers too: decode entities everywhere.
            s["title"] = clean(s.get("title", ""))
            s["angle"] = result["angle"]
            s["bullets"] = result["bullets"]
            if result["debate"]:
                s["debate"] = result["debate"]
            meta = s.get("meta") or {}
            meta["gemini_enrich"] = ENRICH_FLAG
            s["meta"] = meta
            done += 1
            print(f"  [{done}] {s['title'][:70]}")
        time.sleep(1)
    with open(args.input, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f"done: {done} enriched, wrote {args.input}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
