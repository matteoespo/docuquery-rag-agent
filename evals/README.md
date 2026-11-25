# Evals

Measures the agent end to end against a local Ollama, so changes to prompts,
retrieval or models can be compared with numbers instead of impressions.

```bash
uv run python -m evals.run                                   # synthetic corpus
uv run python -m evals.run --compare evals/baselines/synthetic.json
uv run python -m evals.run --dataset local --compare evals/baselines/local.json
uv run python -m evals.run --cases lookup-q7-voltage,followup-kx-speed
```

Each run works in a temporary directory with its own Chroma DB and PDF folder;
`data/` is never written. Web search is stubbed (the run records that the agent
*would* have searched, but nothing is sent to DuckDuckGo) and LangSmith tracing
is forced off. Results go to `evals/results/` (git-ignored).

## Datasets

| Dataset | Corpus | Cases |
|---|---|---|
| `synthetic` | Three generated manuals for fictional products (`evals/corpus.py`). Answers can only come from the documents. Zorvex Q7 and Q9 are deliberately similar with different values. | lookups, Q7-vs-Q9 distractors, troubleshooting, cross-document comparisons, follow-ups with history, unanswerable, out of scope |
| `local` | The PDFs in your `data/pdfs` (copied read-only). The questions target the autonomous-driving ontology review paper; the PDF itself isn't in the repo. | lookups across pages, a table, one unanswerable |

Case format (`evals/datasets/*.jsonl`):

```json
{"id": "distractor-q9-filter", "kind": "distractor",
 "question": "What is the part number of the Zorvex Q9 filter cartridge?",
 "sources": [["zorvex_q9_manual.pdf", 3]],
 "must_contain": ["zf-310"], "must_not_contain": ["zf-220"]}
```

Optional fields: `history` (prior turns), `expect_route: "out_of_scope"`,
`expect_refusal: true` (the documents don't answer it; the agent must say so).
Matching ignores case and whitespace; a nested list in `must_contain` means
"any of these".

## Metrics

Scoring is deterministic (`evals/scoring.py`, unit-tested in CI); no LLM judges.

| Metric | Meaning |
|---|---|
| `answer_accuracy` | Required facts present, forbidden ones absent; refusals for unanswerable cases; blocked for out-of-scope |
| `route_accuracy` | Answered vs blocked as expected |
| `retrieval_hit_rate` | An expected (file, page) is among the retrieved chunks |
| `citation_accuracy` | The answer cites an expected (file, page) |
| `hallucinated_citation_rate` | The answer cites a (file, page) that was never retrieved |
| `web_search_rate_answerable` | Share of document-answerable questions that went to web search anyway (should be 0) |
| `avg_llm_calls`, `median_latency_s`, `p90_latency_s` | Cost and speed per question |

## Workflow

1. Run with `--compare` against the baseline before and after a change.
2. If the change is an improvement you keep, refresh the baseline:
   `--out evals/baselines/<dataset>.json`.
3. After changing `scoring.py`, re-apply it to saved results without calling the model:
   `--rescore evals/baselines/<dataset>.json`.

`evals/baselines/synthetic.json` is committed. `evals/baselines/local.json` is
git-ignored: it depends on your `data/pdfs` and quotes your documents.

Small models aren't perfectly deterministic even at temperature 0, so treat a
difference of one case as noise and look at consistent movements.
