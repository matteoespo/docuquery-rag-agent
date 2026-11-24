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
    "not provide", "n't provide", "not available", "not specif", "n't specif",
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


def _file_key(name: str) -> str:
    """Models often rewrite file names (e.g. collapse a double space): compare loosely."""
    return normalize(name)


def _pages(page: str | None) -> set[str]:
    """ "3" -> {"3"}; "2-3" -> {"2", "3"}; "2, 5" -> {"2", "5"}; None -> set()."""
    if not page:
        return set()
    out = set()
    for part in re.split(r"[,;&]|\band\b", page):
        bounds = [b for b in re.findall(r"\d+", part)]
        if len(bounds) == 2 and "-" in part:
            out.update(str(n) for n in range(int(bounds[0]), int(bounds[1]) + 1))
        else:
            out.update(bounds)
    return out


def _same_source(cited: tuple[str, str | None], file: str, page) -> bool:
    return _file_key(cited[0]) == _file_key(file) and str(page) in _pages(cited[1])


def _invented(citation, retrieved: set, retrieved_files: set, result: dict) -> bool:
    source, page = citation
    if source.startswith(("http://", "https://")):
        return source not in result.get("web_sources", [])
    if _file_key(source) not in {_file_key(f) for f in retrieved_files}:
        return True
    pages = _pages(page)
    retrieved_pages = {p for f, p in retrieved if _file_key(f) == _file_key(source)}
    return bool(pages) and not (pages & retrieved_pages)


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

    retrieved_files = {f for f, _ in retrieved}
    return {
        "route_ok": route_ok,
        "answer_ok": answer_ok,
        # None = not applicable to this case
        "retrieval_hit": any((f, str(p)) in retrieved for f, p in sources) if sources else None,
        "citation_ok": any(_same_source(c, f, p) for c in citations for f, p in sources) if sources else None,
        # Invented: a file never retrieved, a page never retrieved, or a URL that no web
        # result supplied. A file cited without a page is incomplete, not invented
        # (citation_ok still requires the page).
        "hallucinated_citation": any(_invented(c, retrieved, retrieved_files, result) for c in citations),
        "web_search": "websearch" in result["nodes"],
        # Retrieval vs generation: do the retrieved chunks contain the required facts?
        "context_has_answer": (
            answer_contains(" ".join(result.get("retrieved_text", [])), case["must_contain"], [])
            if case.get("must_contain") else None
        ),
    }
