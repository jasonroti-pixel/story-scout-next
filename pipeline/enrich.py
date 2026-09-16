"""
Story Scout Next — enrichment module.
spaCy NER + Canadian flag, VADER sentiment, Sumy LexRank summary,
datasketch MinHash LSH dedupe, category assignment.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

_nlp = None
_sia = None

CANADIAN_LOCATION_HINTS = {
    "canada", "canadian", "toronto", "ontario", "vancouver", "british columbia",
    "bc", "montreal", "quebec", "calgary", "alberta", "ottawa", "manitoba",
    "saskatchewan", "halifax", "nova scotia", "edmonton", "winnipeg",
    "victoria", "yukon", "nunavut", "newfoundland", "labrador", "pei",
    "prince edward island", "new brunswick", "northwest territories",
    "mississauga", "brampton", "hamilton", "london", "kitchener", "waterloo",
    "gatineau", "laval", "surrey", "burnaby", "richmond", "saskatoon",
    "regina", "st. john's", "charlottetown", "whitehorse", "yellowknife",
    "iqaluit", "gta", "greater toronto", "trudeau", "parliament hill",
}

CANADIAN_ORG_HINTS = {
    "cbc", "ctv", "global news", "globe and mail", "toronto star", "cp24",
    "radio-canada", "canadiens", "maple leafs", "blue jays", "raptors",
    "canucks", "oilers", "flames", "senators", "jets", "roughriders",
    "argos", "alouettes", "stampeders", "elks", "tiger-cats", "redblacks",
    "bank of canada", "cra", "rcmp", "csis", "parliament", "house of commons",
}

CATEGORY_KEYWORDS: dict[str, list[str]] = {'THE LIST': ['weird',
              'bizarre',
              'strange',
              'odd',
              'viral',
              'goes viral',
              'not the onion',
              'unusual',
              'quirky',
              'absurd',
              'outrageous',
              'caught on camera',
              'mistaken',
              'prank'],
 'ENTERTAINMENT': ['celebrity',
                   'movie',
                   'film',
                   'actor',
                   'actress',
                   'singer',
                   'music',
                   'album',
                   'netflix',
                   'disney',
                   'hulu',
                   'oscar',
                   'emmy',
                   'grammy',
                   'concert',
                   'tour',
                   'trailer',
                   'box office',
                   'premiere',
                   'billboard',
                   'taylor swift',
                   'beyonce',
                   'itunes',
                   'streaming',
                   'tv show',
                   'reality tv',
                   'red carpet',
                   'hollywood',
                   'awards',
                   'festival'],
 'BREAKOUT WATCH': ['rising',
                    'breakout',
                    'up-and-coming',
                    'viral star',
                    'debut',
                    'first album',
                    'rookie',
                    'newcomer',
                    'emerging',
                    'next big'],
 'LIFESTYLE CHAT': ['health',
                    'wellness',
                    'recipe',
                    'food',
                    'diet',
                    'fitness',
                    'relationship',
                    'dating',
                    'parenting',
                    'home',
                    'travel',
                    'lifestyle',
                    'self-care',
                    'mental health',
                    'uplifting'],
 'CANADIAN NEWS': ['canada',
                   'canadian',
                   'ottawa',
                   'trudeau',
                   'parliament',
                   'toronto',
                   'vancouver',
                   'montreal',
                   'alberta',
                   'ontario',
                   'quebec',
                   'federal',
                   'provincial',
                   'premier'],
 'TECH': ['tech',
          'ai',
          'artificial intelligence',
          'software',
          'app',
          'startup',
          'silicon',
          'google',
          'apple',
          'microsoft',
          'meta',
          'openai',
          'chip',
          'cyber',
          'bitcoin',
          'crypto',
          'gadget'],
 'SPORTS': ['nhl',
            'nba',
            'mlb',
            'cfl',
            'soccer',
            'hockey',
            'basketball',
            'baseball',
            'football',
            'tennis',
            'golf',
            'olympics',
            'game',
            'playoff',
            'championship',
            'score',
            'trade',
            'draft'],
 'CLOSER': ['feel-good',
            'heartwarming',
            'inspiring',
            'hero',
            'kindness',
            'rescue',
            'reunion',
            'charity',
            'donation',
            'miracle']}


def _get_nlp():
    global _nlp
    if _nlp is None:
        import spacy
        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            _nlp = spacy.blank("en")
    return _nlp


def _get_sia():
    global _sia
    if _sia is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        _sia = SentimentIntensityAnalyzer()
    return _sia


def make_story_id(url: str, title: str = "") -> str:
    raw = (url or title or "").strip().lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# Strong talk-radio hints that should not be overridden by Canadian place names.
STRONG_CATEGORY_HINTS = {
    "ENTERTAINMENT",
    "TECH",
    "SPORTS",
    "THE LIST",
    "BREAKOUT WATCH",
    "LIFESTYLE CHAT",
    "CLOSER",
}

# Politics / policy / local-news signals that legitimately warrant CANADIAN NEWS.
CA_NEWS_SIGNALS = {
    "parliament",
    "trudeau",
    "premier",
    "federal",
    "provincial",
    "election",
    "policy",
    "legislation",
    "minister",
    "budget",
    "housing",
    "mortgage",
    "bank of canada",
    "interest rate",
    "transit",
    "ttc",
    "mayor",
    "city council",
    "strike",
    "rcmp",
    "immigration",
    "healthcare",
    "bill c-",
}


def assign_category(text: str, hint: str | None = None) -> str:
    """Assign a board category from keywords + feed hint.

    Respect strong entertainment/tech/sports/list hints even when Canadian
    cities or people appear. Prefer CANADIAN NEWS only for politics/policy/
    local-news signals or CBC Canada-style hints. Weak keyword scores defer
    to the hint; zero scores with no hint fall back to THE LIST.
    """
    blob = (text or "").lower()
    scores: dict[str, int] = {}
    for cat, words in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for w in words if w in blob)
    best = max(scores, key=scores.get)
    best_score = scores[best]

    # Prefer category_hint when keyword evidence is weak.
    if hint and hint in CATEGORY_KEYWORDS and best_score < 2:
        return hint

    if best_score == 0:
        if hint and hint in CATEGORY_KEYWORDS:
            return hint
        return "THE LIST"

    # Do not force CANADIAN NEWS over a strong non-CA hint unless politics/policy.
    if hint in STRONG_CATEGORY_HINTS and best == "CANADIAN NEWS":
        politics = sum(1 for s in CA_NEWS_SIGNALS if s in blob)
        if politics == 0:
            return hint
        # Politics present: still prefer hint if the hint category also scored.
        if scores.get(hint, 0) >= 1 and politics < 2:
            return hint

    # CBC Canada-style / explicit CA hint with politics → CANADIAN NEWS
    if hint == "CANADIAN NEWS" and best_score < 2:
        return "CANADIAN NEWS"

    return best


def extract_entities(text: str) -> dict[str, Any]:
    people: list[str] = []
    organizations: list[str] = []
    locations: list[str] = []
    try:
        nlp = _get_nlp()
        doc = nlp((text or "")[:8000])
        for ent in getattr(doc, "ents", []):
            label = ent.label_
            val = ent.text.strip()
            if not val or len(val) < 2:
                continue
            if label == "PERSON":
                people.append(val)
            elif label == "ORG":
                organizations.append(val)
            elif label in ("GPE", "LOC", "FAC"):
                locations.append(val)
    except Exception:
        pass

    def uniq(seq: list[str], limit: int = 12) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in seq:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                out.append(item)
            if len(out) >= limit:
                break
        return out

    people_u = uniq(people)
    orgs_u = uniq(organizations)
    locs_u = uniq(locations)
    blob = (text or "").lower()
    is_canadian = False
    for hint in CANADIAN_LOCATION_HINTS | CANADIAN_ORG_HINTS:
        if hint in blob:
            is_canadian = True
            break
    if not is_canadian:
        for loc in locs_u + orgs_u:
            if loc.lower() in CANADIAN_LOCATION_HINTS or loc.lower() in CANADIAN_ORG_HINTS:
                is_canadian = True
                break
    return {
        "people": people_u,
        "organizations": orgs_u,
        "locations": locs_u,
        "is_canadian": is_canadian,
    }


def analyze_sentiment(text: str) -> dict[str, Any]:
    try:
        sia = _get_sia()
        scores = sia.polarity_scores(text or "")
        compound = float(scores.get("compound", 0.0))
    except Exception:
        compound = 0.0
    if compound >= 0.05:
        label = "positive"
    elif compound <= -0.05:
        label = "negative"
    else:
        label = "neutral"
    return {"compound": round(compound, 4), "label": label}


def summarize(text: str, sentences: int = 3) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    try:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lex_rank import LexRankSummarizer
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = LexRankSummarizer()
        sents = summarizer(parser.document, sentences)
        out = " ".join(str(s) for s in sents).strip()
        if out:
            return out
    except Exception:
        pass
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(parts[:sentences]).strip()


def build_bullets(text: str, n: int = 3) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    bullets = [p.strip() for p in parts if len(p.strip()) > 20][:n]
    if not bullets:
        bullets = [text[:180] + ("…" if len(text) > 180 else "")]
    return bullets


def _trim_hook(text: str, lo: int = 120, hi: int = 220) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) > hi:
        cut = text[: hi - 1].rsplit(" ", 1)[0].rstrip(",;:—-")
        return cut + "…"
    return text


def suggest_angle(title: str, summary: str, category: str) -> str:
    """Arcade-style 1–2 sentence radio hook (why care / debate / shelf life).

    No template prefixes like "Listener bait:" — aim ~120–220 chars when a
    summary exists. CLOSER stays category CLOSER for UI filters; voice is
    kicker/goodbye energy in the hook itself.
    """
    t = (title or "").strip()
    s = (summary or "").strip()

    why = {
        "THE LIST": "Ask the phones: would you film it, flee it, or pretend you saw nothing?",
        "ENTERTAINMENT": "Shelf life through drive time — who is overrated and who actually delivered?",
        "BREAKOUT WATCH": "Name-drop them now so you can claim you called it first.",
        "LIFESTYLE CHAT": "Easy phone-in: is this smart living or lifestyle cosplay?",
        "CANADIAN NEWS": "Make it local in one sentence — who pays, who waits, who shrugs?",
        "TECH": "Explain it like a coworker Slack rant: helpful tool or creep factor?",
        "SPORTS": "Hot-take window is open — who is carrying, who is hiding?",
        "CLOSER": "Kicker energy: leave them smiling on the way to commercial.",
    }
    closer_note = "CLOSER: THE KICKER/GOODBYES — "
    tail = why.get(category, "Worth ninety seconds if the room lights up.")

    if s:
        first = re.split(r"(?<=[.!?])\s+", s)[0].strip()
        if first and first[-1] not in ".!?":
            first += "."
        if category == "CLOSER":
            hook = f"{closer_note}{first} {tail}"
        else:
            hook = f"{first} {tail}"
        hook = _trim_hook(hook)
        if len(hook) < 120 and t:
            extra = f"{t}. {tail}" if category != "CLOSER" else f"{closer_note}{t}. {tail}"
            hook = _trim_hook(extra)
        return hook

    if t:
        if category == "CLOSER":
            return _trim_hook(f"{closer_note}{t}. {tail}")
        return _trim_hook(f"{t}. {tail}")
    if category == "CLOSER":
        return "CLOSER: THE KICKER/GOODBYES — warm exit that still feels earned."
    return "Talkable beat with room for a thirty-second caller take."


def suggest_debate(title: str, category: str) -> str:
    if category in ("THE LIST", "LIFESTYLE CHAT"):
        return "Would you do this / try this? Why or why not?"
    if category == "ENTERTAINMENT":
        return "Overrated or underrated — where do you land?"
    if category == "SPORTS":
        return "Hot take: who is actually carrying the team?"
    if category == "TECH":
        return "Helpful innovation or privacy nightmare?"
    if category == "CANADIAN NEWS":
        return "Does this change how you see the story locally?"
    return "Agree or disagree — make your case in 30 seconds."


def score_story(
    title: str,
    summary: str,
    category: str,
    entities: dict[str, Any],
    sentiment: dict[str, Any],
    source_type: str = "news",
) -> float:
    score = 50.0
    if entities.get("is_canadian"):
        score += 5
    if category in ("THE LIST", "ENTERTAINMENT", "CLOSER"):
        score += 8
    if source_type == "social":
        score += 3
    people = entities.get("people") or []
    score += min(8, len(people) * 2)
    compound = abs(float(sentiment.get("compound") or 0))
    score += compound * 10
    length = len((summary or "") + (title or ""))
    if 80 <= length <= 1200:
        score += 5
    return round(min(99.0, max(1.0, score)), 1)


class StoryDeduper:
    """MinHash LSH near-duplicate clustering."""

    def __init__(self, threshold: float = 0.55, num_perm: int = 128):
        self.threshold = threshold
        self.num_perm = num_perm
        self._lsh = None
        self._minhashes: dict[str, Any] = {}
        self._clusters: dict[str, str] = {}
        self._sizes: dict[str, int] = {}

    def _ensure(self):
        if self._lsh is None:
            from datasketch import MinHashLSH
            self._lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)

    @staticmethod
    def _shingles(text: str, n: int = 3) -> set[str]:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(tokens) < n:
            return set(tokens) or {"_empty_"}
        return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}

    def add(self, story_id: str, text: str) -> tuple[str, int]:
        self._ensure()
        from datasketch import MinHash
        mh = MinHash(num_perm=self.num_perm)
        for sh in self._shingles(text):
            mh.update(sh.encode("utf-8"))
        result = self._lsh.query(mh)
        if result:
            cluster_id = self._clusters.get(result[0], result[0])
        else:
            cluster_id = story_id
            self._lsh.insert(story_id, mh)
        self._minhashes[story_id] = mh
        self._clusters[story_id] = cluster_id
        self._sizes[cluster_id] = self._sizes.get(cluster_id, 0) + 1
        return cluster_id, self._sizes[cluster_id]

    def related_count(self, cluster_id: str) -> int:
        return max(0, self._sizes.get(cluster_id, 1) - 1)


def enrich_story(
    raw: dict[str, Any],
    deduper: StoryDeduper | None = None,
    pipeline_version: str = "1.1.0",
) -> dict[str, Any]:
    """Enrich a raw ingest dict into the Story Scout schema."""
    title = (raw.get("title") or "").strip()
    body = (raw.get("body") or raw.get("summary") or "").strip()
    url = (raw.get("url") or "").strip()
    source = (raw.get("source") or "").strip()
    source_type = raw.get("source_type") or "news"
    category_hint = raw.get("category_hint")
    slot = raw.get("slot") or "am"
    date = raw.get("date") or datetime.now(timezone.utc).astimezone().date().isoformat()

    combined = f"{title}. {body}"
    category = assign_category(combined, category_hint)
    entities = extract_entities(combined)
    sentiment = analyze_sentiment(combined)
    summary = summarize(body or title)
    bullets = build_bullets(summary or body, n=3)
    angle = suggest_angle(title, summary, category)
    debate = suggest_debate(title, category)
    score = score_story(title, summary, category, entities, sentiment, source_type)

    story_id = raw.get("id") or make_story_id(url, title)
    cluster_id = story_id
    related_count = 0
    if deduper is not None:
        cluster_id, size = deduper.add(story_id, f"{title} {summary}")
        related_count = max(0, size - 1)

    now = datetime.now(timezone.utc).isoformat()
    published = raw.get("source_published_at") or raw.get("published") or now

    story: dict[str, Any] = {
        "id": story_id,
        "date": date,
        "slot": slot,
        "category": category,
        "title": title,
        "angle": angle,
        "bullets": bullets,
        "debate": debate,
        "source": source,
        "source_type": source_type,
        "url": url,
        "score": score,
        "is_backup": bool(raw.get("is_backup", False)),
        "entities": entities,
        "sentiment": sentiment,
        "summary": summary,
        "cluster_id": cluster_id,
        "related_count": related_count,
        "clips": raw.get("clips") or [],
        "meta": {
            "ingested_at": now,
            "source_published_at": published,
            "pipeline_version": pipeline_version,
        },
    }
    return story
