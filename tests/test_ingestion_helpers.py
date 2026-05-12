"""Pure helpers from ingestion (no PDF I/O)."""
from ai.ingestion import table_to_markdown


def test_table_to_markdown_basic():
    table = [
        ["Name", "Value"],
        ["A", "1"],
        ["B", "2"],
    ]
    md = table_to_markdown(table)
    assert "| Name | Value |" in md
    assert "|---|" in md or "| --- |" in md  # separator row
    assert "| A | 1 |" in md
    assert "| B | 2 |" in md


def test_table_to_markdown_empty_cells():
    table = [["H1", "H2"], [None, "x"]]
    md = table_to_markdown(table)
    assert "H1" in md and "H2" in md
    assert "x" in md
