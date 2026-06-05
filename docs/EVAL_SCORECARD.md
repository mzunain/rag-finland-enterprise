# Retrieval Evaluation Scorecard

Last verified: 2026-06-06.

This scorecard reports the deterministic seeded retrieval gate. It is a regression baseline for known golden cases, not a claim of production accuracy on unseen customer data.

## Summary

| Metric | Result | Threshold | Status |
| --- | ---: | ---: | --- |
| Total cases | 5 | - | Passing |
| Cases passed | 5/5 | 100% | Passing |
| Case pass rate | 100% | 100% | Passing |
| Citation recall | 100% | 100% | Passing |
| Grounded-answer accuracy | 100% | 100% | Passing |
| No-answer accuracy | 100% | 100% | Passing |
| Missing predictions | 0 | 0 | Passing |

## Coverage

| Dimension | Cases | Notes |
| --- | ---: | --- |
| English | 3 | HR answer, technical answer, and no-answer coverage |
| Finnish | 1 | Finnish annual leave retrieval with stemming support |
| Swedish | 1 | Swedish legal/DPA retrieval |
| HR-docs | 3 | Includes one no-answer case |
| Legal-docs | 1 | DPA citation case |
| Technical-docs | 1 | Restore/SLA citation case |

## Reproduce

```bash
./run eval
```

The command runs:

```bash
cd backend
PYTHONPATH=. ../.venv/bin/python -m app.evaluation \
  --cases evals/retrieval_golden.json \
  --corpus evals/seed_corpus.json \
  --min-citation-recall 1.0 \
  --min-no-answer-accuracy 1.0 \
  --min-grounded-accuracy 1.0 \
  --min-case-pass-rate 1.0 \
  --pretty
```

## How To Extend The Gate

- Add multilingual cases to `backend/evals/retrieval_golden.json`.
- Add source chunks to `backend/evals/seed_corpus.json`.
- Keep no-answer cases in the suite so the retriever is tested for restraint, not only recall.
- Promote weak production or demo answers from the Review Center into eval cases.
- Run the scheduled `Retrieval Evaluation` GitHub Actions workflow after retrieval, ingestion, chunking, or prompt changes.
