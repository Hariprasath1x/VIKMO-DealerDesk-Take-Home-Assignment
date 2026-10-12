# VIKMO DealerDesk — AI/ML Intern Track

**Candidate Submission**: Antigravity  
**Track**: AI / ML Intern  
**Assignment**: VIKMO DealerDesk Take-Home Assignment  
**API Contract**: Strictly adheres to `API_CONTRACT.md`  

---

## 1. Problem Statement & Overview

VIKMO DealerDesk is a comprehensive B2B distribution and parts management platform designed for independent automotive spare-parts dealers across South India. The platform integrates:
1. **Core B2B Backend**: PostgreSQL-backed catalogue, idempotent seeding, dealer profiles, and inventory management.
2. **Dealer Assistant (AI)**: An intelligent conversational agent powered by Groq (`openai/gpt-oss-120b`) and dense RAG (`all-MiniLM-L6-v2` + ChromaDB) supporting semantic parts search, live stock checks, and draft order creation.
3. **Demand Forecasting & Reorder Intelligence (ML)**: A machine-learning forecasting engine predicting 4-week demand for 40 key SKUs, coupled with safety stock and reorder point optimization ($ROP$).
4. **Reliable Order Engine (Optional A2)**: Atomic stock deductions with row-level locks, two-decimal GST calculations, and an immutable state machine.
5. **Supplier Sync Engine (Optional B)**: A resilient, two-stage atomic synchronization engine connecting to upstream supplier catalogues with exponential backoff and rate-limit recovery.
6. **Dealer Portal (Optional E)**: A responsive, professional React 19 + TypeScript + Vite + Tailwind CSS + Recharts single-page application.

---

## 2. Architecture & Technology Stack

```
                                  +---------------------------------------+
                                  |   React + TypeScript Dealer Portal    |
                                  |      (Vite / Tailwind / Recharts)     |
                                  +-------------------+-------------------+
                                                      | HTTP / JSON REST
                                                      v
                                  +---------------------------------------+
                                  |    Django REST Framework Gateway      |
                                  +---+-------------------------------+---+
                                      |                               |
       +------------------------------+--------+                      |
       |                              |        |                      |
       v                              v        v                      v
+--------------+              +--------------+ +---------------+ +---------------+
| Core Service |              | Order Engine | | Supplier Sync | | Forecast/ROP  |
| - Products   |              | - Row Locks  | | - 2-Stage Sync| | - GBDT Hybrid |
| - Dealers    |              | - RoundHalfUp| | - 429 Backoff | | - 4-Wk Demand |
| - Inventory  |              | - Idempotency| | - Atomic Feed | | - Live Stock  |
+-------+------+              +-------+------+ +---------------+ +-------+-------+
        |                             |                                  |
        +-----------------------------+----------------------------------+
                                      |
                                      v
                        +---------------------------+
                        |   PostgreSQL Database     |
                        |   (Single Source of Truth)|
                        +---------------------------+
                                      ^
                                      | Live Stock & Prices
+-------------------------------------+-----------------------------------+
|                     AI Dealer Assistant Subsystem                       |
|                                                                         |
|  [User Query] ---> [Groq LLM: openai/gpt-oss-120b]                      |
|                           |                                             |
|                     Tool Calls:                                         |
|                     - search_parts()  ---> ChromaDB (all-MiniLM-L6-v2)  |
|                     - check_stock()   ---> PostgreSQL (Live ORM)        |
|                     - create_draft()  ---> OrderService                 |
+-------------------------------------------------------------------------+
```

### Technology Matrix
- **Language**: Python 3.11+
- **Backend Framework**: Django 4.2+ & Django REST Framework 3.15+
- **Database**: PostgreSQL 16 (via `psycopg3` & `dj-database-url`)
- **LLM Provider**: Groq API
- **LLM Model**: `openai/gpt-oss-120b` (fast, deterministic tool-calling reasoning)
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384-dim dense vectors, run locally)
- **Vector Database**: ChromaDB 0.5+ (HNSW persistent index with cosine distance)
- **ML Frameworks**: `scikit-learn`, `numpy`, `pandas`, `lightgbm`
- **Frontend Stack**: React 19, TypeScript, Vite 8, Tailwind CSS v4, Recharts, Lucide Icons

---

## 3. Fresh-Clone Setup & Run Contract

The backend adheres strictly to the assignment's exact startup contract without requiring Docker:

### 1. Prerequisites
- Python 3.11+
- PostgreSQL instance (local or hosted)

### 2. Environment Configuration
Create a `.env` file from `.env.example`:
```bash
cp .env.example .env
```
Ensure `DATABASE_URL` and `GROQ_API_KEY` are configured:
```env
DATABASE_URL=postgres://user:password@localhost:5432/dealerdesk
GROQ_API_KEY=gsk_your_groq_api_key_here
DJANGO_SECRET_KEY=production-secret-key-placeholder
SUPPLIER_API_URL=http://127.0.0.1:8099
SUPPLIER_API_KEY=dev-supplier-key
```

### 3. Execution Sequence (Grading Contract)
```bash
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py seed_data
python manage.py seed_data
python manage.py runserver 0.0.0.0:8000 --noreload
```

> [!NOTE]
> `python manage.py seed_data` is completely idempotent. Running it repeatedly updates existing records without creating duplicates. It seeds:
> - 600 catalogue products from `data/catalogue.csv`
> - 25 dealer accounts from `data/dealers.csv`
> - Synchronizes all 600 product embeddings into ChromaDB vector storage.

---

## 4. AI Dealer Assistant Design & Security

### Subsystem Architecture
- **Provider & Model**: Groq API using `openai/gpt-oss-120b`.
- **Dense Vector Search**: Powered by `sentence-transformers/all-MiniLM-L6-v2` executing locally in PyTorch. Embeddings are stored in a persistent ChromaDB collection (`chroma_db/`).
- **Tool Calling**: Native JSON tool calls:
  1. `search_parts(query, category, vehicle)`: Semantic search over product specifications, joined with live PostgreSQL prices and inventory.
  2. `check_stock(sku)`: Direct relational query against live inventory.
  3. `create_draft_order(dealer_id, items)`: Creates unconfirmed draft orders (`DRAFT` status).

### Security & Prompt Injection Defenses
`data/catalogue.csv` contains real adversarial prompt injection attempts (`CHN-1037` attempting to grant 90% discounts with `VIKMO-FREE-90`, and `BDY-1070` attempting to trigger admin mode without stock checks). DealerDesk implements defense-in-depth:
1. **Input Sanitization**: Regex filtering strips injection patterns before text is embedded or fed to LLM context (`core/assistant/guardrails.py`).
2. **XML Isolation Boundaries**: Catalogue descriptions are wrapped inside `<catalogue_data>` tags with explicit system instructions treating them as untrusted passive data.
3. **Capability Sandboxing**: The assistant toolset **only exposes draft order creation**. It cannot confirm orders, alter prices, or bypass database stock checks.
4. **Post-Generation Output Filters**: Validates numerical claims against tool outputs and redacts unauthorized coupon codes (`core/assistant/guardrails.py`).

### Empirical Retrieval Benchmark
Evaluated using [`core/assistant/evaluate_retrieval.py`](core/assistant/evaluate_retrieval.py):
- **Recall@1**: 50.0%
- **Recall@5**: 100.0%
- **Mean Reciprocal Rank (MRR)**: 0.7292
- **Out-of-Domain Rejection Rate**: 100.0%

---

## 5. Demand Forecasting & Inventory Optimization (ML)

### Problem Horizon
- **Target SKUs**: Exactly the 40 SKUs specified in `data/lead_times.csv`.
- **Target Horizon**: 4 forecast weeks starting `2026-09-28` (`2026-09-28`, `2026-10-05`, `2026-10-12`, `2026-10-19`).
- **Artifact**: `ml/forecast.csv` (160 rows, schema: `sku,week_start,forecast_units`).

### Multi-Cluster Modeling Strategy
- **Core Established SKUs (34 SKUs)**: Direct multi-step `GradientBoostingRegressor` with 14 engineered features (lags $t-1 \dots t-4, t-52$, rolling means/std, upcoming promotions, and signed distance to Diwali).
- **Intermittent SKUs (4 SKUs with >35% zero sales)**: Median-smoothed estimators preventing over-prediction of zero intervals.
- **New SKUs (2 SKUs with 6 weeks history)**: Exponential moving average ($\alpha=0.3$) scaled by category promotional lift.

### Calendar & Festival Shift Handling
In 2025, Diwali fell on October 21 (overlapping the forecast horizon). In 2026, Diwali falls on November 8 (3 weeks after the horizon ends). Rather than using naive calendar month/week features that would project a false October surge, DealerDesk computes:
$$\text{weeks\_to\_diwali} = \frac{\text{week\_start} - \text{diwali\_date}}{7}$$
capturing the true festive ramp-up function.

### Anti-Leakage Protocol & Rolling-Origin Backtest Results
Validated across a 4-fold chronological rolling backtest (`forecasting/backtest.py`):
```text
=================================================================
CHRONOLOGICAL BACKTEST BENCHMARK RESULTS (Across All Validation Folds)
=================================================================
Baseline 1: Last Observed Value     | WAPE: 38.45% | MAE: 13.28 | RMSE: 20.44
Baseline 2: Recent 4-Week Average   | WAPE: 29.74% | MAE: 10.27 | RMSE: 15.74
Baseline 3: Same Week Last Year     | WAPE: 34.28% | MAE: 11.84 | RMSE: 18.14
Candidate: Segmented GBDT Hybrid    | WAPE: 27.96% | MAE:  9.66 | RMSE: 14.98
=================================================================
```
**Relative Improvement**: The GBDT Hybrid achieves a **27.3% error reduction** over Last Value and **6.0% error reduction** over Recent Average.

### Strict Reorder Formula (`GET /api/reorder-suggestions/`)
Computed strictly according to `API_CONTRACT.md` §10:
- $L$: Lead time in weeks from `data/lead_times.csv`
- $\text{lead\_time\_demand} = \sum_{w=1}^{L} \text{forecast\_units}_w$
- $\sigma$: Sample standard deviation ($ddof=1$) over the last 12 weeks of sales history
- $\text{safety\_stock} = \lceil 1.65 \times \sigma \times \sqrt{L} \rceil$
- $\text{reorder\_point} = \text{lead\_time\_demand} + \text{safety\_stock}$
- $\text{reorder\_qty} = \max(0, \lceil \text{reorder\_point} - \text{current\_stock} \rceil)$ using live stock from PostgreSQL.

---

## 6. Optional Features Implemented

### A2: Reliable Order Engine
- **Atomic State Transitions**: `DRAFT` $\to$ `CONFIRMED` $\to$ `DISPATCHED` $\to$ `DELIVERED` (or `CANCELLED`).
- **Overselling Prevention**: Concurrency control using PostgreSQL row-level locks (`Product.objects.select_for_update()`). All-or-nothing stock deduction.
- **GST Monetary Precision**: Computed using Python `Decimal` with `ROUND_HALF_UP` per line item (18% GST).
- **Idempotency**: Supports `Idempotency-Key` headers with SHA-256 payload verification.

### B: Resilient Supplier Synchronization (`POST /api/sync/supplier/`)
- **Two-Stage Atomic Sync**: Stage 1 fetches and validates all cursor-paginated pages; Stage 2 applies catalogue changes atomically within a database transaction.
- **Rate-Limit Resilience**: Handles HTTP 429 and transient 5xx responses with exponential backoff and `Retry-After` header parsing.
- **Deduplication**: Resolves duplicate SKUs by selecting the latest `updated_at` record. Local inventory stock is strictly preserved.

### E: Complete React Dealer Portal (`frontend/`)
- Single-page application built with React 19, TypeScript, Vite, Tailwind CSS v4, and Recharts.
- Features: Dashboard with live KPIs, Parts Catalogue with faceted search and stock adjustments, Order Management with GST breakdowns, AI Dealer Assistant chat with tool execution cards, and Forecast Demand Charts with reorder recommendations.
- Communicates exclusively with the Django REST API (`http://127.0.0.1:8000`).

---

## 7. Verification & Automated Test Suite

### 1. Django Test Suite (PostgreSQL)
```bash
python manage.py test --noinput
```
**Result**: **62/62 tests passed** (0 errors, 0 failures).

### 2. Contract Smoke Test (`smoke_test.py`)
```bash
# AI/ML Track Check
python smoke_test.py --base-url http://localhost:8000 --track aiml
# Result: 10/10 checks passed

# All Contract Check (including Order Engine & Supplier Sync)
python smoke_test.py --base-url http://localhost:8000 --all
# Result: 12/12 checks passed
```

### 3. Frontend Production Build
```bash
cd frontend
npm install
npm run build
```
**Result**: Clean production compilation in under 300ms; `0 errors`.

---

## 8. Frontend Portal Setup & Run Guide

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in any modern web browser. The Vite development proxy directs `/api` requests to `http://127.0.0.1:8000`.

To build the static distribution:
```bash
npm run build
```
Assets are generated in `frontend/dist/`.

---

## 9. Video Walkthrough

- **Walkthrough Link**: `https://youtu.be/placeholder-vikmo-dealerdesk-walkthrough` *(Placeholder: replace with unlisted video link prior to final submission)*
- **Topics Covered**:
  1. System architecture and relational database schema
  2. Assistant tool-calling loop (`search_parts`, `check_stock`, `create_draft_order`) and ChromaDB dense RAG
  3. Prompt injection defenses and live grounding guarantees
  4. GBDT demand forecasting, rolling backtest validation, and safety stock math
  5. Live portal walkthrough (Dashboard, Catalogue, Orders, Assistant, Forecast)

---

## 10. Submission Checklist & Repository Hygiene

- [x] `manage.py` and `requirements.txt` reside at the repository root
- [x] Runs on fresh PostgreSQL using standard sequence without Docker
- [x] Zero API keys, passwords, or secrets committed in Git history
- [x] `.env.example` contains only clean placeholder templates
- [x] `data/` directory and CSV source files remain strictly untouched
- [x] Django database migrations committed (`core/migrations/`)
- [x] Forecast artifact committed (`ml/forecast.csv` with exactly 160 rows)
- [x] `smoke_test.py --track aiml` passes 10/10 checks
- [x] `smoke_test.py --all` passes 12/12 checks
- [x] All 62 backend test cases pass on PostgreSQL
- [x] Frontend compiles cleanly (`npm run build`) with zero TypeScript errors
- [x] `DECISIONS.md` answers all 8 required AI/ML evaluation questions with exact code citations
