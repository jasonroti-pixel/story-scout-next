"""
Story Scout Next — enrichment module.
spaCy NER + Canadian flag, VADER sentiment, Sumy LexRank summary,
datasketch MinHash LSH dedupe, category assignment.
"""

from __future__ import annotations

import hashlib
import json
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


_ml_clf = None  # (vectorizer, classifier, sections) or False when unavailable

# Section order the vendored model was trained on (models/section-clf-v1).


def _get_ml_clf():
    """Lazily load the vendored section classifier (models/section-clf-v1).

    Returns (vec, clf, sections) or None when the model files or sklearn
    are unavailable; callers must fall back to assign_category.
    """
    global _ml_clf
    if _ml_clf is None:
        try:
            import pickle
            from pathlib import Path

            d = Path(__file__).resolve().parent / "models" / "section-clf-v1"
            vec = pickle.loads((d / "tfidf.pkl").read_bytes())
            clf = pickle.loads((d / "section_clf.pkl").read_bytes())
            sections = json.loads((d / "meta.json").read_text())["sections"]
            _ml_clf = (vec, clf, sections)
        except Exception:
            _ml_clf = False
    return _ml_clf or None


def classify_section_ml(text: str):
    """Classify a story into a rundown section with the fitted model.

    Returns (section, probs) or None when the model is unavailable.
    Any inference error returns None so the caller can fall back to
    keyword classification.

    NOTE: the model was trained on an archive that never used TECH or
    SPORTS, so its classes_ cover only 6 sections. Probabilities are
    mapped back onto the full section order (unseen classes get 0.0);
    callers should route TECH/SPORTS hints around this function.
    """
    ml = _get_ml_clf()
    if ml is None:
        return None
    try:
        vec, clf, sections = ml

        X = vec.transform([text or ""])
        proba = clf.predict_proba(X)[0]
        probs = {sec: 0.0 for sec in sections}
        for cls, p in zip(clf.classes_, proba):
            if cls in probs:
                probs[cls] = float(p)
        best = max(sections, key=probs.__getitem__)
        return best, {s: round(probs[s], 4) for s in sections}
    except Exception:
        return None


# Classes the fitted model never saw in training (absent from the archive).
# Stories with these feed hints bypass the ML and use keyword classification.
ML_UNSEEN_SECTIONS = {"TECH", "SPORTS"}

_stacked_clf = None  # (vectorizer, classifier, sections) or False when unavailable


def _get_stacked_clf():
    """Lazily load the stacked section classifier (models/section-clf-stacked-v1).

    Same TF-IDF text features as section-clf-v1 plus 12 Jev features
    (top_p, topic_conf, air_suitability, canadian_angle, freshness, and a
    7-dim topic_section one-hot). Returns (vec, clf, sections) or None;
    callers fall back to classify_section_ml.
    """
    global _stacked_clf
    if _stacked_clf is None:
        try:
            import pickle
            from pathlib import Path

            d = Path(__file__).resolve().parent / "models" / "section-clf-stacked-v1"
            vec = pickle.loads((d / "tfidf.pkl").read_bytes())
            clf = pickle.loads((d / "section_clf.pkl").read_bytes())
            sections = json.loads((d / "meta.json").read_text())["sections"]
            _stacked_clf = (vec, clf, sections)
        except Exception:
            _stacked_clf = False
    return _stacked_clf or None


def _jev_questions(today: str) -> dict:
    """The 5 Jev questions the stacked model was trained on (iter8 battery)."""
    return {
        "is_top_story": {
            "type": "noul",
            "instructions": (
                "Is this one of the day's biggest, most consequential stories, "
                "the kind that leads the show? About one quarter of the "
                "day's stories make THE LIST. In this show's history, THE LIST stories are "
                "dominated by national politics and government action (the White House, "
                "Congress, courts and major lawsuits), world affairs (China, wars, trade "
                "deals), major tech/AI stories with wide impact, and big economic news. "
                "Examples of top stories: "
                "'Trump signs executive order to ban certain Canadian goods, including alcohol'; "
                "'25 states sue Trump over forced-labour tariffs'; "
                "'FBI investigating 153 million US and Canadian driver's licenses leaked on "
                "Russian cybercrime forum'. Examples of smaller stories: "
                "'NYC City Hall ditches iconic green doors, breaks wedding photo tradition'; "
                "'Why Your Kitchen Tools Keep Vanishing Into the Void'."
            ),
            "criteria": {
                "true": "belongs with the day's biggest headlines",
                "false": "a smaller story, however interesting",
            },
        },
        "topic_section": {
            "type": "choice",
            "instructions": (
                "Which topic section would the show's producer run this story in? "
                "This is only about the story's topic and energy, not its importance. "
                "Use the examples under each option as your guide."
            ),
            "criteria": {
                "ENTERTAINMENT": (
                    "Celebrity-centered: stars, Hollywood, movies and film, music, TV, fan "
                    "reactions, celebrity backlash and controversies. If a celebrity or the "
                    "entertainment industry is the subject, it lives here, even when the story "
                    "is outrageous. "
                    "Examples: 'Sandra Bullock Reveals Hollywood Auditions Were so Disturbing, "
                    "'Perverts' Asked Her To Drop Her Pants'; "
                    "'Macklemore speaks out after being dropped from Ed Sheeran's tour following "
                    "his 'Free Palestine' speech'. "
                    "But if it is fundamentally about a shocking or absurd event that merely "
                    "happens to involve a famous person, it is BREAKOUT WATCH."
                ),
                "BREAKOUT WATCH": (
                    "Viral, shocking, absurd, or outrageous stories with talker energy: the kind "
                    "of thing blowing up on social media that everyone will be discussing. This "
                    "includes substantive news with a wow edge, not just silly items. "
                    "Examples: 'LA blew $60M on homeless 'fix' - it housed just three units'; "
                    "'Apocalyptic video shows wildfire flames surrounding train'. "
                    "Quick-hit viral fuel, not discussion fodder: if the story carries a real "
                    "debate or discussion angle, it is almost never Breakout Watch. "
                    "If the story is fundamentally about a celebrity or the entertainment "
                    "industry, it is ENTERTAINMENT; if it is a light end-of-show kicker, it is CLOSER."
                ),
                "LIFESTYLE CHAT": (
                    "Lifestyle and culture conversation, often driven by new research or studies: "
                    "health, wellness, relationships, dating, parenting, food, home, the brain. "
                    "'New study finds...' framing is the classic tell. Conversational and "
                    "relatable, built for listener opinions and calls. "
                    "Examples: 'Depression Actually Rewires Your Brain, New Study Finds'; "
                    "'Think your country's rigged? New study says that's wrecking your mood'."
                ),
                "CANADIAN NEWS": (
                    "Canada-first news, politics, and national issues that hit home for Canadian "
                    "listeners: Parliament, the Prime Minister, premiers, trade deals, sovereignty. "
                    "Examples: 'Carney presses 10 EU countries to ratify Canada trade deal'; "
                    "'Carney says US trade terms could box Canada in'."
                ),
                "TECH": (
                    "Stories fundamentally about technology, AI, gadgets, or the internet; "
                    "not viral (BREAKOUT WATCH) and not health or science news (LIFESTYLE CHAT). "
                    "Example: a hands-on review of a new AI gadget launch."
                ),
                "SPORTS": (
                    "Only the big wins or huge Canadian sports news; no scores or stats unless "
                    "record-breaking; athlete hot takes, controversies, and sports figures in the news. "
                    "Example: a record-breaking championship win."
                ),
                "CLOSER": (
                    "The end-of-show kicker: light, fun, heartwarming, or quirky 'and finally' stories "
                    "that send listeners off smiling, including light celebrity items. Wildlife "
                    "rescues, anniversaries and throwbacks, good-news oddities. Earnest or silly, "
                    "it must feel like a smile. "
                    "Examples: 'Three critically endangered American Red Wolf pups born at the "
                    "Saint Louis Zoo were fostered into a wild family'; "
                    "'Cult classic Donnie Darko will return to theaters in 4K for its 25th "
                    "anniversary in October'. "
                    "Never heavy news and never outrage; those belong elsewhere."
                ),
            },
        },
        "air_suitability": {
            "type": "score",
            "instructions": (
                "How central is this story to today's show? About 4 in 10 stories end up as backups, so be "
                "selective: reserve the top levels for stories that clearly earn a slot."
            ),
            "criteria": [
                "Cut: does not belong in the rundown at all",
                "Weak backup: thin, hold only if desperate",
                "Solid backup: decent reserve if time allows",
                "Likely core: probably earns a slot",
                "Must-air: the show is weaker without it",
            ],
        },
        "canadian_angle": {
            "type": "noul",
            "instructions": "Does this story have a Canadian angle or direct relevance to a Canadian audience?",
            "criteria": {
                "true": "mentions Canada or Canadians, or affects them directly",
                "false": "no Canadian connection",
            },
        },
        "freshness": {
            "type": "noul",
            "instructions": f"Today is {today}. Is this story fresh enough for today's show?",
            "criteria": {
                "true": "published within the last 48 hours, or evergreen with no expiry",
                "false": "older than 48 hours and time-bound to a past event",
            },
        },
    }


def jev_section_features(title: str, body: str, api_key: str, today: str):
    """Fetch the 12 Jev features the stacked model needs, best-effort.

    One POST to the Jev API with the 5 training questions. Returns the
    12-dim feature list or None on ANY failure (network, auth, timeout,
    malformed response) so the caller can fall back to the text-only model.
    Never raises.
    """
    try:
        import urllib.request

        state = {"title": title or "", "body": (body or "")[:2000], "today": today}
        payload = json.dumps(
            {"state": state, "model": "jev-latest", "questions": _jev_questions(today)},
            separators=(",", ":"),
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://api.typesafe.ai/v1/systemone",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        a = data.get("answers") or {}
        topic = (a.get("topic_section") or {}).get("choice")
        if topic is None:
            return None
        onehot = [1.0 if topic == s else 0.0 for s in
                  ["ENTERTAINMENT", "BREAKOUT WATCH", "LIFESTYLE CHAT",
                   "CANADIAN NEWS", "TECH", "SPORTS", "CLOSER"]]
        return [
            float((a.get("is_top_story") or {}).get("noul", 0.5)),
            float((a.get("topic_section") or {}).get("confidence", 0.0)),
            float((a.get("air_suitability") or {}).get("score", 3.0)),
            float((a.get("canadian_angle") or {}).get("noul", 0.0)),
            float((a.get("freshness") or {}).get("noul", 0.8)),
        ] + onehot
    except Exception:
        return None


def classify_section_stacked(text: str, jev_feats):
    """Classify with the stacked model (text TF-IDF + 12 Jev features).

    Returns (section, probs) or None when the model is unavailable, the
    feature layout is wrong, or inference fails. Callers fall back to
    classify_section_ml, then keywords.
    """
    ml = _get_stacked_clf()
    if ml is None or not jev_feats or len(jev_feats) != 12:
        return None
    try:
        import numpy as np
        from scipy.sparse import csr_matrix, hstack

        vec, clf, sections = ml
        X = hstack([vec.transform([text or ""]), csr_matrix(np.array(jev_feats).reshape(1, -1))])
        proba = clf.predict_proba(X)[0]
        probs = {sec: 0.0 for sec in sections}
        for cls, p in zip(clf.classes_, proba):
            if cls in probs:
                probs[cls] = float(p)
        best = max(sections, key=probs.__getitem__)
        return best, {s: round(probs[s], 4) for s in sections}
    except Exception:
        return None


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
    section_model = "keywords"
    section_probs: dict[str, float] | None = None
    if category_hint in ML_UNSEEN_SECTIONS:
        # The fitted model never saw TECH/SPORTS in training; trust the
        # feed hint via the keyword path for these.
        category = assign_category(combined, category_hint)
        section_model = "keywords-hint"
    else:
        # Stacked model when Jev features were fetched upstream (ml-stacked-v1,
        # 0.62 test); text-only model otherwise (ml-v1, 0.54); keywords last.
        stacked = classify_section_stacked(f"{title} {body}", raw.get("_jev"))
        if stacked is not None:
            category, section_probs = stacked
            section_model = "ml-stacked-v1"
        else:
            ml_result = classify_section_ml(f"{title} {body}")
            if ml_result is not None:
                category, section_probs = ml_result
                section_model = "ml-v1"
            else:
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
            "section_model": section_model,
            "section_probs": section_probs,
        },
    }
    return story
