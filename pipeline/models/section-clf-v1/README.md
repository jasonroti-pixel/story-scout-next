# section-clf-v1 — section classifier for Story Scout Next

Logistic regression on TF-IDF(title + body, 1-2 grams, 20k features).
No API calls, fully offline, no history needed at inference time.

- Honest test accuracy on the unseen week (>= 2026-09-19): **0.544**
- Previous keyword classifier on the same week: 0.304

## Design notes

**6 classes, not 8.** The training archive (2,726 aired stories, 2026-07-09
to 2026-09-25) never used TECH or SPORTS as sections, so the model only
predicts the other six. The pipeline handles this as a hybrid (enrich.py):

- Stories with a TECH or SPORTS feed hint bypass the model and use the
  keyword classifier, which respects strong feed hints.
- Everything else goes through the model (`section_model: "ml-v1"` in
  story meta); any model failure falls back to keywords.
- `section_probs` in story meta carries the model's 8-section probability
  map (TECH/SPORTS always 0.0 from the model).

**No previous-edition feature.** An earlier variant added the previous
edition's section histogram (+2 points in the lab, 0.566), but it was
dropped: in training "previous edition" meant yesterday's *curated rundown*,
while in production it would be the last *raw ingest batch* — different
semantics, and the feature herded predictions toward the batch mix.

## Provenance

Trained 2026-09-27 from the frozen production archive (`daily-goods-rundowns`)
via `~/workspace/skills/typesafe/bin/train-text-clf.py`.

Caveat: the model encodes the former producer's section patterns. Retrain
as the show's taste evolves or it will quietly go stale.
