"""Deterministic scoring for eval cases (no LLM judge).

Matching ignores case and whitespace, so "36 V DC" matches "36v". In
``must_contain``, a nested list means "any of these alternatives".
"""

import re
from pathlib import PurePath

CITATION_RE = re.compile(r"\[Source:\s*([^,\]]+?)\s*(?:,\s*Page:\s*([^\]]+?))?\s*\]", re.IGNORECASE)

# Contracted forms ("n't mention") cover don't/doesn't/isn't/aren't.
REFUSAL_MARKERS = [
    "don't know", "do not know", "don't have information", "do not have information",
    "n't have any information", "have no information", "not mention", "n't mention", "no mention",
    "not mentioned", "n't mentioned", "no information", "not contain", "n't contain",
    "not provided", "n't provide", "not available", "not specified", "n't specify",
    "not stated", "n't say", "not include", "n't include", "unable to find",
    "could not find", "couldn't find", "not found", "no details",
    "no specific information", "cannot find", "can't find",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("’", "'").lower())


def _matches(answer_norm: str, expected) -> bool:
    if isinstance(expected, list):
        return any(_matches(answer_norm, alt) for alt in expected)
    return normalize(expected) in answer_norm


def answer_contains(answer: str, must_contain: list, must_not_contain: list) -> bool:
    norm = normalize(answer)
    return all(_matches(norm, e) for e in must_contain) and not any(
        _matches(norm, e) for e in must_not_contain
    )


def is_refusal(answer: str) -> bool:
    norm = normalize(answer)
    return any(normalize(m) in norm for m in REFUSAL_MARKERS)


def parse_citations(answer: str) -> list[tuple[str, str | None]]:
    """[(source, page)] from "[Source: x.pdf, Page: 3]" style citations."""
    out = []
    for source, page in CITATION_RE.findall(answer):
        source = source.strip()
        if not source.startswith(("http://", "https://")):
            source = PurePath(source).name
        out.append((source, page.strip() if page else None))
    return out


def _same_source(cited: tuple[str, str | None], file: str, page) -> bool:
    return cited[0] == file and cited[1] == str(page)


def score_case(case: dict, result: dict) -> dict:
    """Score one case. ``result`` has: route, answer, retrieved [(file, page)], nodes."""
    expect_route = case.get("expect_route", "answer")
    route_ok = result["route"] == expect_route
    sources = [tuple(s) for s in case.get("sources", [])]
    retrieved = {(f, str(p)) for f, p in result["retrieved"]}
    citations = parse_citations(result["answer"])

    if expect_route == "out_of_scope":
        answer_ok = route_ok
    elif case.get("expect_refusal"):
        answer_ok = route_ok and is_refusal(result["answer"])
    else:
        answer_ok = route_ok and answer_contains(
            result["answer"], case.get("must_contain", []), case.get("must_not_contain", [])
        )

    file_citations = [c for c in citations if not c[0].startswith(("http://", "https://"))]
    return {
        "route_ok": route_ok,
        "answer_ok": answer_ok,
        # None = not applicable to this case
        "retrieval_hit": any((f, str(p)) in retrieved for f, p in sources) if sources else None,
        "citation_ok": any(_same_source(c, f, p) for c in citations for f, p in sources) if sources else None,
        "hallucinated_citation": any((c[0], c[1]) not in retrieved for c in file_citations),
        "web_search": "websearch" in result["nodes"],
    }
