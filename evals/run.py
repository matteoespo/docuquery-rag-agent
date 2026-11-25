"""Run the eval set against the real agent and a local Ollama.

    uv run python -m evals.run                      # synthetic corpus (default)
    uv run python -m evals.run --dataset local      # your PDFs in data/pdfs (read-only copy)
    uv run python -m evals.run --compare evals/baselines/synthetic.json
    uv run python -m evals.run --cases lookup-q7-voltage,followup-kx-speed
    uv run python -m evals.run --rescore evals/baselines/synthetic.json   # after changing scoring

Everything runs in a temporary directory (its own Chroma DB and PDF folder);
data/ is never written. Web search is stubbed: the run records that the agent
*would* have searched, but nothing is sent to DuckDuckGo. LangSmith tracing is
forced off.
"""

import argparse
import asyncio
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATASETS = {
    "synthetic": ROOT / "evals" / "datasets" / "synthetic.jsonl",
    "local": ROOT / "evals" / "datasets" / "local_paper.jsonl",
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", choices=DATASETS, default="synthetic")
    p.add_argument("--cases", help="comma-separated case ids to run (default: all)")
    p.add_argument("--ollama-url", default="http://localhost:11434")
    p.add_argument("--model", help="chat model to evaluate (default: LLM_MODEL from settings/.env)")
    p.add_argument("--out", type=Path, help="results JSON path (default: evals/results/<dataset>-<time>.json)")
    p.add_argument("--compare", type=Path, help="earlier results JSON to compare the summary against")
    p.add_argument("--rescore", type=Path, help="re-apply current scoring to a saved results JSON (no model calls)")
    return p.parse_args()


def rescore(path: Path) -> None:
    from evals.scoring import score_case

    data = json.loads(path.read_text())
    for row in data["rows"]:
        row["result"]["retrieved"] = [tuple(x) for x in row["result"]["retrieved"]]
        row["score"] = score_case(row["case"], row["result"])
    old_summary, data["summary"] = data["summary"], summarize(data["rows"])
    print_report(data["rows"], data["summary"], {"summary": old_summary})
    path.write_text(json.dumps(data, indent=2, default=str))
    print(f"\nRescored {path}")


def configure_environment(tmp: Path, ollama_url: str, model: str | None) -> None:
    # Must happen before importing backend modules: settings are read at import.
    os.environ.update(
        DB_DIR=str(tmp / "db"),
        MANUAL_PATH=str(tmp / "pdfs"),
        OLLAMA_BASE_URL=ollama_url,
        LANGSMITH_TRACING="false",
        SKIP_IMAGE_CAPTIONING="true",
    )
    if model:
        os.environ["LLM_MODEL"] = model
    sys.path.insert(0, str(ROOT / "backend"))


class _NoResultsDDGS:
    """Stands in for DDGS: the websearch node still runs (and is recorded) but sends nothing."""

    def text(self, *args, **kwargs):
        return []


def build_corpus(dataset: str, pdf_dir: Path) -> None:
    if dataset == "synthetic":
        from evals.corpus import build_synthetic_corpus

        build_synthetic_corpus(pdf_dir)
        return
    sources = sorted((ROOT / "data" / "pdfs").glob("*.pdf"))
    if not sources:
        sys.exit("No PDFs in data/pdfs for --dataset local.")
    pdf_dir.mkdir(parents=True)
    for src in sources:
        shutil.copy(src, pdf_dir / src.name)


async def run_case(agent, case: dict) -> dict:
    from langchain_core.callbacks import BaseCallbackHandler

    class CountLLMCalls(BaseCallbackHandler):
        calls = 0

        def on_chat_model_start(self, *args, **kwargs):
            self.calls += 1

    counter = CountLLMCalls()
    state = {"query": case["question"], "documents": [], "answer": "",
             "chat_history": case.get("history", []), "retries": 0}
    nodes, final = [], {}
    start = time.perf_counter()
    async for update in agent.astream(state, config={"callbacks": [counter]}, stream_mode="updates"):
        for node, output in update.items():
            nodes.append(node)
            final.update(output or {})
    latency = time.perf_counter() - start

    local_docs = [
        d for d in final.get("documents", [])
        if not str(d.metadata.get("source", "")).startswith(("http://", "https://"))
    ]
    retrieved = [(Path(str(d.metadata.get("source", ""))).name, d.metadata.get("page")) for d in local_docs]
    return {
        "route": "out_of_scope" if "block" in nodes else "answer",
        "answer": final.get("answer", ""),
        "search_query": final.get("search_query"),
        "retrieved": retrieved,
        "retrieved_text": [d.page_content for d in local_docs],
        "nodes": nodes,
        "llm_calls": counter.calls,
        "latency_s": round(latency, 2),
    }


def _rate(values) -> float | None:
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 3) if values else None


def summarize(rows: list[dict]) -> dict:
    answerable = [r for r in rows if r["case"].get("expect_route", "answer") == "answer"
                  and not r["case"].get("expect_refusal")]
    by_kind = defaultdict(list)
    for r in rows:
        by_kind[r["case"]["kind"]].append(r["score"]["answer_ok"])
    latencies = [r["result"]["latency_s"] for r in rows]
    return {
        "cases": len(rows),
        "answer_accuracy": _rate(r["score"]["answer_ok"] for r in rows),
        "route_accuracy": _rate(r["score"]["route_ok"] for r in rows),
        "retrieval_hit_rate": _rate(r["score"]["retrieval_hit"] for r in rows),
        # Chunk level: the retrieved text contains every required fact.
        "answer_in_context_rate": _rate(r["score"].get("context_has_answer") for r in rows),
        # Generation quality when retrieval did its job.
        "accuracy_when_in_context": _rate(
            r["score"]["answer_ok"] for r in rows if r["score"].get("context_has_answer")
        ),
        "citation_accuracy": _rate(r["score"]["citation_ok"] for r in rows),
        "hallucinated_citation_rate": _rate(r["score"]["hallucinated_citation"] for r in rows),
        # Questions the documents answer should never need the web.
        "web_search_rate_answerable": _rate(r["score"]["web_search"] for r in answerable),
        "avg_llm_calls": round(statistics.mean(r["result"]["llm_calls"] for r in rows), 2),
        "median_latency_s": round(statistics.median(latencies), 2),
        "p90_latency_s": round(sorted(latencies)[max(0, int(len(latencies) * 0.9) - 1)], 2),
        "answer_accuracy_by_kind": {k: _rate(v) for k, v in sorted(by_kind.items())},
    }


def _fmt(v) -> str:
    return "-" if v is None else ("✓" if v is True else ("✗" if v is False else str(v)))


def print_report(rows: list[dict], summary: dict, compare: dict | None) -> None:
    print(f"\n{'case':28} {'kind':16} answer route hit  ctx  cite web  calls  secs")
    for r in rows:
        s, res = r["score"], r["result"]
        print(f"{r['case']['id'][:28]:28} {r['case']['kind'][:16]:16} "
              f"{_fmt(s['answer_ok']):6} {_fmt(s['route_ok']):5} {_fmt(s['retrieval_hit']):4} "
              f"{_fmt(s.get('context_has_answer')):4} "
              f"{_fmt(s['citation_ok']):4} {_fmt(s['web_search']):4} {res['llm_calls']:5}  {res['latency_s']:5}")
    print("\nSummary")
    old = (compare or {}).get("summary", {})
    for key, value in summary.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                delta = _delta(v, old.get(key, {}).get(k))
                print(f"    {k:22} {_fmt(v)}{delta}")
        else:
            print(f"  {key:30} {_fmt(value)}{_delta(value, old.get(key))}")


def _delta(new, old) -> str:
    if not isinstance(new, (int, float)) or not isinstance(old, (int, float)) or isinstance(new, bool):
        return ""
    diff = round(new - old, 3)
    return f"   ({'+' if diff >= 0 else ''}{diff} vs baseline {old})" if diff else "   (=)"


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "unknown"


async def main_async(args) -> None:
    tmp = Path(tempfile.mkdtemp(prefix="docuquery-eval-"))
    configure_environment(tmp, args.ollama_url, args.model)
    try:
        from ai.agent import load_agent
        from ai.ingestion import ingest_manual
        from core.config import settings
        from evals.scoring import score_case

        cases = [json.loads(line) for line in DATASETS[args.dataset].read_text().splitlines() if line.strip()]
        if args.cases:
            wanted = set(args.cases.split(","))
            cases = [c for c in cases if c["id"] in wanted]

        build_corpus(args.dataset, tmp / "pdfs")
        ingest_manual()
        agent = load_agent()

        rows = []
        with patch("ai.nodes.websearch.DDGS", _NoResultsDDGS):
            for i, case in enumerate(cases, 1):
                print(f"[{i}/{len(cases)}] {case['id']}", flush=True)
                result = await run_case(agent, case)
                rows.append({"case": case, "result": result, "score": score_case(case, result)})

        summary = summarize(rows)
        compare = json.loads(args.compare.read_text()) if args.compare else None
        print_report(rows, summary, compare)

        out = args.out or ROOT / "evals" / "results" / f"{args.dataset}-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "dataset": args.dataset, "model": settings.llm_model, "embedding_model": settings.embedding_model,
            "retrieval_k": settings.retrieval_k, "commit": git_commit(),
            "summary": summary, "rows": rows,
        }, indent=2, default=str))
        print(f"\nResults written to {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    args = parse_args()
    if args.rescore:
        rescore(args.rescore)
    else:
        asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
