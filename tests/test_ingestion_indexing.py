"""Ingestion indexing: per-file stable chunk IDs, skip unchanged files, replace stale vectors."""

import pymupdf
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding

import backend.ai.ingestion as ingestion


class CountingEmbeddings(DeterministicFakeEmbedding):
    calls: int = 0

    def embed_documents(self, texts):
        self.calls += len(texts)
        return super().embed_documents(texts)


def make_pdf(path, pages: list[str]) -> str:
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return str(path)


@pytest.fixture
def env(tmp_path, monkeypatch):
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    embeddings = CountingEmbeddings(size=16)
    monkeypatch.setattr(ingestion.settings, "db_dir", str(tmp_path / "db"))
    monkeypatch.setattr(ingestion.settings, "manual_path", str(pdf_dir))
    monkeypatch.setattr(ingestion, "get_embeddings", lambda: embeddings)
    return pdf_dir, embeddings


def all_vectors() -> dict[str, dict]:
    got = ingestion._get_vector_db()._collection.get(include=["metadatas"])
    return dict(zip(got["ids"], got["metadatas"]))


def test_chunk_ids_number_per_page():
    chunks = [Document(page_content="x", metadata={"page": p}) for p in (1, 1, 2, 1)]
    assert ingestion._chunk_ids("h", chunks) == ["h_1_0", "h_1_1", "h_2_0", "h_1_2"]


def test_adding_a_file_does_not_change_existing_ids(env):
    pdf_dir, _ = env
    a = make_pdf(pdf_dir / "a.pdf", ["alpha page one", "alpha page two"])
    assert ingestion.ingest_manual([a]) == [a]
    ids_after_a = set(all_vectors())

    b = make_pdf(pdf_dir / "b.pdf", ["bravo page one"])
    # Full-directory run: a is already indexed and must be skipped.
    assert ingestion.ingest_manual() == [b]

    vectors = all_vectors()
    assert ids_after_a <= set(vectors)
    assert sum(m["source"] == a for m in vectors.values()) == len(ids_after_a)
    assert sum(m["source"] == b for m in vectors.values()) == 1


def test_reingesting_unchanged_file_skips_embedding(env):
    pdf_dir, embeddings = env
    a = make_pdf(pdf_dir / "a.pdf", ["alpha"])
    ingestion.ingest_manual([a])
    before = all_vectors()

    embeddings.calls = 0
    assert ingestion.ingest_manual([a]) == []
    assert embeddings.calls == 0
    assert all_vectors() == before


def test_overwritten_file_replaces_its_vectors(env):
    pdf_dir, _ = env
    a = make_pdf(pdf_dir / "a.pdf", ["old one", "old two", "old three"])
    ingestion.ingest_manual([a])

    make_pdf(pdf_dir / "a.pdf", ["new content"])
    assert ingestion.ingest_manual([a]) == [a]

    db = ingestion._get_vector_db()
    docs = db._collection.get(where={"source": a}, include=["documents"])["documents"]
    assert len(docs) == 1
    assert "new content" in docs[0]


def test_legacy_vectors_without_hash_are_replaced(env):
    pdf_dir, _ = env
    a = make_pdf(pdf_dir / "a.pdf", ["alpha"])
    ingestion._get_vector_db().add_documents(
        [Document(page_content="legacy", metadata={"source": a, "page": 1})],
        ids=["legacy_0"],
    )

    ingestion.ingest_manual([a])

    vectors = all_vectors()
    assert "legacy_0" not in vectors
    assert all(m.get("file_hash") for m in vectors.values())


# Upload endpoint

@pytest.fixture
def upload_client(tmp_path, monkeypatch):
    import api.routers as routers

    calls = []
    monkeypatch.setattr(routers.settings, "manual_path", str(tmp_path / "uploads"))
    monkeypatch.setattr(routers, "ingest_manual", lambda paths: calls.append(paths) or [])
    app = FastAPI()
    app.include_router(routers.router)
    return TestClient(app), tmp_path / "uploads", calls


def test_upload_rejects_whole_batch_without_saving(upload_client):
    client, upload_dir, calls = upload_client
    resp = client.post("/api/upload", files=[
        ("files", ("good.pdf", b"%PDF-1.4 ok", "application/pdf")),
        ("files", ("bad.pdf", b"not a pdf", "application/pdf")),
    ])
    assert resp.status_code == 400
    assert list(upload_dir.iterdir()) == []
    assert calls == []


def test_upload_ingests_only_uploaded_files(upload_client):
    client, upload_dir, calls = upload_client
    upload_dir.mkdir()
    (upload_dir / "existing.pdf").write_bytes(b"%PDF-1.4 old")

    resp = client.post("/api/upload", files=[
        ("files", ("new.pdf", b"%PDF-1.4 new", "application/pdf")),
    ])
    assert resp.status_code == 200
    assert calls == [[str(upload_dir / "new.pdf")]]
