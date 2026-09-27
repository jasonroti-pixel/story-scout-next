# section-clf-stacked-v1

Stacked section classifier: TF-IDF(title+body, 1-2 grams, 20k, min_df=3)
logistic regression (C=1.0) plus 12 Jev features:

- top_p, topic_conf, air_suitability, canadian_angle, freshness
- 7-dim one-hot of Jev's topic_section choice

Jev features come from one API call per story with the 5 iter8 battery
questions (defined in `pipeline/enrich.py::_jev_questions`).

**Honest test accuracy: 0.6225** on the unseen week (355 stories >= 2026-09-19),
vs 0.5437 for the text-only model and 0.304 for the keyword classifier.

**Degradation path (best-effort by design):** the Jev fetch in
`pipeline/ingest.py::_fetch_jev_features` never raises and never blocks the
run. Missing `TYPESAFE_API_KEY`, API errors, timeouts, or malformed
responses all fall back to section-clf-v1 (text-only), then keywords.
TECH/SPORTS feed hints skip the Jev call and bypass the model entirely
(the training archive never used those sections).

**Files:** `tfidf.pkl`, `section_clf.pkl`, `meta.json`
**Trained:** 2026-09-27 (train < 2026-09-19, test >= 2026-09-19)
**Training originals:** `~/workspace/skills/typesafe/artifacts/section-clf-stacked-v1/`
