"""
Central application settings loaded from environment variables.

Uses Pydantic BaseSettings for validation, type coercion, and .env support.
All backend modules should import ``settings`` from here instead of calling
``os.getenv()`` directly.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide configuration with validated defaults."""

    # ── Ollama ──
    ollama_base_url: str = "http://ollama:11434"
    llm_model: str = "llama3.2:3b"
    vision_model: str = "moondream"
    embedding_model: str = "nomic-embed-text"

    # ── Paths ──
    db_dir: str = "data/chroma_db"
    manual_path: str = "data/pdfs/"

    # ── Ingestion tuning ──
    skip_image_captioning: bool = False
    min_image_bytes: int = 5000
    min_image_dimension: int = 100
    max_vision_workers: int = 2
    max_pdf_workers: int = 4
    chroma_batch_size: int = 100

    # ── Upload limits ──
    max_upload_size_mb: int = 50
    max_upload_files: int = 10

    # ── CORS ──
    cors_origins: list[str] = ["http://localhost:8501", "http://web:8501"]

    # ── Retrieval ──
    retrieval_k: int = 3
    max_retries: int = 2

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
