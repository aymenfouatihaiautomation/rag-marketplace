# RAG-Powered Intelligent Marketplace

A full **Retrieval-Augmented Generation (RAG)** system for a tech marketplace,
featuring two conversational assistants:

- **Seller assistant** — automates product-listing creation via guided conversation
- **Buyer assistant** — acts as a technical expert with strict product filtering

Built with LangChain, ChromaDB, LLaMA 3.3 70B (via Groq), FastAPI.

> Final-year engineering project — ENSTTIC Oran.
> **92% category-detection accuracy** · **94.3% attribute completeness** · **~500 ms/turn**

---

## Architecture

```
MySQL (categories + attributes)
   └──► BAAI/bge-small-en-v1.5 embeddings
        └──► ChromaDB (384-d vectors, HNSW)
             └──► LLaMA 3.3 70B via Groq
                  └──► FastAPI endpoints
```

## Tech stack

| Layer | Technology |
|---|---|
| Orchestration | LangChain |
| LLM | LLaMA 3.3 70B (Groq LPU) |
| Embeddings | BAAI/bge-small-en-v1.5 (384-d) |
| Vector DB | ChromaDB (HNSW, persistent) |
| Backend | FastAPI + Pydantic structured output |
| Database | MySQL (EAV schema) |
| Frontend | HTML / CSS / vanilla JS |

## Key results

| Metric | Value |
|---|---|
| Category detection (Precision@1) | **92%** (46/50 queries) |
| Attribute completeness | **94.3%** (20 sessions) |
| End-to-end latency | **~500 ms/turn** |

## Getting started

```bash
git clone https://github.com/<your-username>/rag-marketplace.git
cd rag-marketplace
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env with your keys
```

Import `ecommerce_ai.sql` into MySQL, then build the ChromaDB index:

```bash
python save_categories.py
uvicorn app:app --reload
```

Open http://localhost:8000/login.html

## Project structure

```
├── app.py                  # FastAPI entry point
├── database.py             # MySQL connection (reads from .env)
├── embeddings.py           # HuggingFace + Groq keys (reads from .env)
├── vector_store.py         # ChromaDB collections
├── save_categories.py      # One-time indexing script
├── routers/
│   ├── seller.py           # Seller assistant (RAG + structured output + FSM)
│   ├── buyer.py            # Buyer assistant (RAG + requirements accumulation)
│   ├── auth.py             # Login / logout
│   └── products.py         # Product CRUD
├── frontend/                # HTML/CSS/JS pages
├── requirements.txt
├── .env.example             # Template (safe to commit)
└── .gitignore
```

## Default users

| Username  | Password  |
|-----------|-----------|
| admin     | admin123  |
| john_doe  | john1234  |
| jane_doe  | jane1234  |

## API endpoints

| Method | Endpoint           | Description                   |
|--------|---------------------|--------------------------------|
| POST   | /login              | Authenticate user             |
| POST   | /logout             | Invalidate session             |
| POST   | /seller/chat        | Seller AI agent message       |
| POST   | /seller/reset       | Reset seller session          |
| POST   | /buyer/chat         | Buyer AI agent message        |
| POST   | /buyer/reset        | Reset buyer session            |
| GET    | /products/mine      | Get logged-in user's products |
| DELETE | /products/{id}      | Delete product (MySQL+Chroma) |

## Limitations & future work

- Sessions in memory — migrate to Redis for production
- Passwords stored in plain text — switch to bcrypt + JWT
- 92% measured on a small corpus (~20 categories)
- No formal RAGAS evaluation yet
- Planned: HyDE query rewriting, cross-encoder reranking

## Authors

- **Aymen Fouatih** — [LinkedIn](https://www.linkedin.com/in/aymen-fouatih-ai-automation-5790b242a/)
- **Oussama Djebbar Senouci**

Supervised by M. Boumediene Mohammed — ENSTTIC Oran (2025/2026)

## License

MIT
