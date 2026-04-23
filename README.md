# Industrial RAG Agent
This project implements an Agentic RAG system designed to process and query industrial technical documentation. The architecture is fully containerized and designed to run entirely on-premise using local LLMs.

## Architecture Overview
The system follows a modular architecture, decoupling the AI engine from the API layer to ensure scalability and maintainability.

## Technology Stack
**Backend:** FastAPI (Python) for low-latency, asynchronous API handling.

**AI Framework:** LangChain & LangGraph for orchestration of agentic workflows.

**LLM Engine:** Llama 3 (8B) via Ollama for local, privacy-compliant reasoning.

**Embeddings:** nomic-embed-text for high-performance semantic search.

**Vector Database:** ChromaDB for local persistent storage of technical chunks.

**Infrastructure:** Docker & Docker Compose for deployment.

## Features
**Data Privacy (On-Premise):** The entire pipeline runs locally, ensuring that sensitive data never leaves the internal infrastructure.

**Hallucination Mitigation:** Implements a temperature-controlled RAG chain with strict prompt engineering to ensure factual accuracy.

**Scalable Infrastructure:** Microservices-based deployment allows for independent scaling of the API and the inference engine.

**API Validation:** Rigorous input/output validation using Pydantic models.

## Quick Start

**Clone the repository:**

```
git clone https://github.com/yourusername/industrial-rag-agent.git
cd industrial-rag-agent
```
**Deploy the stack:**

```
docker compose up -d
```

**Pull models within the container:**

```
docker exec -it industrial-rag-ollama ollama pull llama3
docker exec -it industrial-rag-ollama ollama pull nomic-embed-text
```

**Access the API Documentation:**

Navigate to http://localhost:8000/docs to test the endpoints via Swagger UI.
