# Retrieval Evaluation

The retrieval evaluation harness scores saved retrieval predictions against golden RAG cases.

Run locally from `backend/`:

```bash
PYTHONPATH=. ../.venv/bin/python -m app.evaluation \
  --cases evals/retrieval_golden.json \
  --corpus evals/seed_corpus.json \
  --pretty
```

Or from the repository root:

```bash
./run eval
```

The gate tracks:

- citation recall against required source documents and pages
- no-answer accuracy for questions the corpus should not answer
- grounded-answer accuracy for answerable questions
- pass rate by language and collection

Golden cases live in `backend/evals/retrieval_golden.json`. Each answerable case should include the smallest set of required citations that proves the answer. No-answer cases should use `"expectation": "no_answer"` and no required citations.

Seed corpus chunks live in `backend/evals/seed_corpus.json`. CI uses the seeded corpus to generate deterministic lexical retrieval predictions, then scores those generated predictions against the golden cases. This catches citation drift, collection filtering mistakes, no-answer regressions, and multilingual retrieval regressions without requiring an external model or database.

GitHub Actions runs the same gate on pull requests, pushes, manual CI launches, and the scheduled `Retrieval Evaluation` workflow at 04:17 UTC every day.

## Promoting Review Center Cases

Admins can turn weak answer feedback into durable eval cases from the Review Center. The `Promote to eval` action creates an active case with the original question, collection, language, answer excerpt, review notes, and the exact citations captured with the feedback. This closes the loop from user-reported answer quality issues into repeatable regression coverage.

The promoted cases are available through:

- `GET /admin/eval-cases` for the Review Center metric and queue
- `POST /admin/reviews/{review_id}/promote-eval` to promote a review
- `GET /admin/eval-cases/export` to download golden-case JSON

Use the exported JSON as a staging input before moving stable cases into `backend/evals/retrieval_golden.json`. Keep promoted cases active while they represent unresolved or recently fixed retrieval behavior, and archive noisy or obsolete cases after policy changes.

## Running Live Promoted Evals

The Review Center can run active promoted cases against the current retrieval stack and persist the run history:

- `POST /admin/eval-runs` runs active promoted cases, optionally filtered by `collection`
- `GET /admin/eval-runs` returns recent runs, latest status, pass-rate trend, and the stored report

Each run stores the evaluated cases, live retrieval predictions, pass/fail status, case pass rate, citation recall, grounded accuracy, and no-answer accuracy. Use this before and after ingestion, connector sync, permission changes, or retrieval tuning to verify that user-reported failures do not regress.

The Launch Center can also schedule these live promoted evals from the UI. When enabled, the backend checks due schedules every `EVAL_SCHEDULER_POLL_SECONDS` seconds, runs active cases for the configured collection, records the latest pass/fail status, and advances the next due time. If no active cases are available, the scheduler records the failure in the schedule state instead of crashing the process.

To save generated predictions for inspection:

```bash
PYTHONPATH=. ../.venv/bin/python -m app.evaluation \
  --cases evals/retrieval_golden.json \
  --corpus evals/seed_corpus.json \
  --write-predictions /tmp/retrieval_predictions.json \
  --pretty
```

Prediction files use this shape:

```json
{
  "predictions": [
    {
      "case_id": "hr-en-annual-leave",
      "outcome": "grounded",
      "citations": [
        { "document": "HR-policy.pdf", "page": 2, "relevance": 0.91 }
      ]
    }
  ]
}
```

Static prediction files are still supported with `--predictions` for debugging or comparing a live retrieval run exported from another environment.
