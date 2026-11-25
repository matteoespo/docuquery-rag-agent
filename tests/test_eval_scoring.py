"""Eval scoring is deterministic and CI-safe (no Ollama needed)."""

import json
from pathlib import Path

from evals.scoring import answer_contains, is_refusal, parse_citations, score_case

DATASETS = Path(__file__).resolve().parents[1] / "evals" / "datasets"


def test_matching_ignores_case_and_whitespace():
    assert answer_contains("It needs 36 V DC.", ["36v"], [])
    assert answer_contains("Hold MODE for 10 seconds", ["10second"], [])


def test_nested_list_means_any_alternative():
    assert answer_contains("wire it as a normally closed contact on X5", [["(nc)", "normally closed"], "x5"], [])
    assert not answer_contains("wire it on X5", [["(nc)", "normally closed"], "x5"], [])


def test_must_not_contain_catches_the_wrong_product():
    assert not answer_contains("Use filter ZF-310, or ZF-220 for older units", ["zf-310"], ["zf-220"])


def test_refusal_detection():
    assert is_refusal("The provided documents do not mention a warranty period.")
    assert is_refusal("I don’t know based on the context.")
    assert is_refusal("I don't have information on the pricing of the KX-200.")
    assert is_refusal("The retrieved context does not provide specific information about it.")
    assert is_refusal("The context provided does not specify the number of layers.")
    assert not is_refusal("The warranty period is 2 years.")


def test_parse_citations_normalizes_paths_and_keeps_urls():
    answer = "36 V [Source: data/pdfs/q7.pdf, Page: 2] and [Source: https://x.com/a]"
    assert parse_citations(answer) == [("q7.pdf", "2"), ("https://x.com/a", None)]


def _result(**kw):
    base = {"route": "answer", "answer": "", "retrieved": [], "nodes": ["contextualize", "retrieve", "generate"]}
    return base | kw


def test_score_case_correct_grounded_answer():
    case = {"kind": "lookup", "sources": [["q7.pdf", 2]], "must_contain": ["36v"]}
    result = _result(answer="It needs 36 V DC [Source: q7.pdf, Page: 2]", retrieved=[("q7.pdf", 2), ("q9.pdf", 2)])
    assert score_case(case, result) == {
        "route_ok": True, "answer_ok": True, "retrieval_hit": True, "citation_ok": True,
        "hallucinated_citation": False, "web_search": False, "context_has_answer": False,
    }


def test_context_has_answer_separates_retrieval_from_generation():
    case = {"kind": "lookup", "sources": [["q7.pdf", 2]], "must_contain": ["36v"]}
    found = _result(answer="I don't know.", retrieved=[("q7.pdf", 2)], retrieved_text=["Input voltage: 36 V DC."])
    missing = _result(answer="I don't know.", retrieved=[("q7.pdf", 2)], retrieved_text=["Maximum current: 14 A."])
    assert score_case(case, found)["context_has_answer"] is True   # generation failure
    assert score_case(case, missing)["context_has_answer"] is False  # retrieval failure


def test_score_case_flags_citation_to_page_never_retrieved_and_web_search():
    case = {"kind": "lookup", "sources": [["q7.pdf", 2]], "must_contain": ["36v"]}
    result = _result(answer="36 V [Source: q7.pdf, Page: 9]", retrieved=[("q7.pdf", 2)],
                     nodes=["contextualize", "retrieve", "websearch", "generate"])
    score = score_case(case, result)
    assert score["citation_ok"] is False
    assert score["hallucinated_citation"] is True
    assert score["web_search"] is True


def test_file_cited_without_page_is_incomplete_not_invented():
    case = {"kind": "lookup", "sources": [["q7.pdf", 2]], "must_contain": ["g3"]}
    score = score_case(case, _result(answer="Terminal G3 [Source: q7.pdf]", retrieved=[("q7.pdf", 2)]))
    assert score["hallucinated_citation"] is False
    assert score["citation_ok"] is False  # still needs the page


def test_file_names_compare_loosely_and_page_ranges_match():
    case = {"kind": "lookup", "sources": [["A Review for  Testing.pdf", 2]], "must_contain": ["five"]}
    result = _result(answer="five layers [Source: A Review for Testing.pdf, Page: 2-3]",
                     retrieved=[("A Review for  Testing.pdf", 2)])
    score = score_case(case, result)
    assert score["citation_ok"] is True
    assert score["hallucinated_citation"] is False


def test_made_up_url_is_invented():
    case = {"kind": "lookup", "sources": [["q9.pdf", 3]], "must_contain": ["zf-310"]}
    score = score_case(case, _result(answer="ZF-310 [Source: https://example.com]", retrieved=[("q9.pdf", 3)]))
    assert score["hallucinated_citation"] is True


def test_score_case_out_of_scope_and_refusal():
    assert score_case({"kind": "oos", "expect_route": "out_of_scope"}, _result(route="out_of_scope"))["answer_ok"]
    assert not score_case({"kind": "oos", "expect_route": "out_of_scope"}, _result())["answer_ok"]
    refusal_case = {"kind": "unanswerable", "expect_refusal": True}
    assert score_case(refusal_case, _result(answer="The documents don't mention a price."))["answer_ok"]
    assert not score_case(refusal_case, _result(answer="It costs 499 EUR."))["answer_ok"]


def test_datasets_are_well_formed():
    for path in DATASETS.glob("*.jsonl"):
        ids = set()
        for line in path.read_text().splitlines():
            case = json.loads(line)
            assert case["id"] not in ids, f"duplicate id {case['id']} in {path.name}"
            ids.add(case["id"])
            assert case["question"] and case["kind"]
            answerable = case.get("expect_route", "answer") == "answer" and not case.get("expect_refusal")
            if answerable:
                assert case.get("sources") and case.get("must_contain"), case["id"]
