# VIKMO DealerDesk — AI/ML Intern Track

**Candidate Submission**: Hariprasath C
**Repository**: [https://github.com/Hariprasath1x/VIKMO-DealerDesk-Take-Home-Assignment](https://github.com/Hariprasath1x/VIKMO-DealerDesk-Take-Home-Assignment)
**Track**: AI / ML Intern
**Assignment**: VIKMO DealerDesk Take-Home Assignment
**API Contract Compliance**: Strictly conforms to `API_CONTRACT.md`

---

## 1. Problem Statement & System Overview

Automotive aftermarket parts distribution across South India faces four operational challenges:
1. **Stock Overselling & Financial Drift**: Concurrent dealer orders over-commit limited inventory, while float arithmetic introduces paisa rounding errors on 18% GST invoices.
2. **Stale Catalogues**: Manual catalogue updates leave inventory pricing and new part introductions out of sync with suppliers.
3. **Repetitive Parts Inquiries**: Dealership counter staff spend hours answering fitment, stock, and pricing queries ("Do you have brake pads for a Duke 390?").
4. **Demand Volatility & Guesswork Reordering**: Demand swings heavily with festive seasons (Diwali) and promotional campaigns, causing stockouts or excess capital lockup.

**DealerDesk** solves these issues through an integrated platform:
- **Core B2B Backend**: PostgreSQL-backed catalogue of 600 products, 25 dealers, inventory management, and draft orders.
- **AI Dealer Assistant**: Grounded conversational assistant with tool calling (`search_parts`, `check_stock`, `create_draft_order`), local semantic embeddings (`sentence-transformers/all-MiniLM-L6-v2`), persistent ChromaDB vector storage, and multi-layer prompt injection defense.
- **Demand Forecasting & Reorder Optimization**: Segmented Gradient Boosting Regressor (GBDT) predicting 4-week demand for 40 SKUs, beating all baselines on a 4-fold chronological rolling backtest (27.96% WAPE), feeding an exact safety-stock and reorder point ($ROP$) engine.
- **Reliable Order Lifecycle (Bonus A2)**: Row-level stock concurrency locks (`select_for_update`), `ROUND_HALF_UP` 18% line-item GST, daily sequential order numbering (`ORD-YYYYMMDD-NNNN`), and idempotent order creation.
- **Resilient Supplier Sync (Bonus B)**: 2-stage atomic catalogue synchronization with exponential backoff, HTTP 429 `Retry-After` compliance, duplicate resolution by `updated_at`, and zero disruption to local stock.
- **Dealer Portal (Bonus E)**: Full React 19 + TypeScript + Vite + Tailwind CSS portal with dashboard analytics, parts catalogue, orders, assistant chat, and forecast reorder views.

---

## 2. Architecture & Data Flow

```mermaid
flowchart TD
    subgraph UI ["Dealer Portal (React 19 / TypeScript / Vite)"]
        portal["Web Dashboard, Catalogue, Chat & Reorder Portal"]
    end

    subgraph API ["Django REST Framework (Port 8000)"]
        health["/api/health/"]
        products["/api/products/"]
        inventory["/api/inventory/"]
        dealers["/api/dealers/"]
        orders["/api/orders/"]
        assistant["/api/assistant/chat/"]
        forecast["/api/forecast/"]
        reorder["/api/reorder-suggestions/"]
        sync["/api/sync/supplier/"]
    end

    subgraph LLM_AI ["AI & Retrieval Subsystem"]
        groq["Groq API (llama-3.3-70b-versatile)"]
        tools["Tool Calling Engine: search_parts, check_stock, create_draft_order"]
        chroma[("ChromaDB Vector Store (all-MiniLM-L6-v2)")]
        guard["Guardrails: Sanitization, XML Bounds, Redaction"]
    end

    subgraph ML_Engine ["Demand Forecasting Engine"]
        train["Segmented GBDT Regressor"]
        artifact[("ml/forecast.csv (160 rows, 40 SKUs)")]
        rop["Safety Stock & Reorder Point Calculator"]
    end

    subgraph DB ["PostgreSQL (Single Source of Truth)"]
        pg[("PostgreSQL Database: Products, Inventory, Dealers, Orders, Sessions")]
    end

    portal -->|HTTP / JSON| API
    assistant --> groq
    groq --> tools
    tools --> chroma
    tools --> guard
    tools -->|Live Stock & Price| pg
    orders -->|Row Locks & GST| pg
    products --> pg
    inventory --> pg
    dealers --> pg
    forecast --> artifact
    reorder --> artifact
    reorder -->|Live Stock| pg
    sync -->|Atomic Upsert| pg
```

---

## 3. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | Modern typing, performance, and library support |
| **Backend Framework** | Django 5.2 & Django REST Framework 3.15 | Robust ORM, migrations, strict serialization |
| **Database** | PostgreSQL 16 (via `psycopg3` & `dj-database-url`) | Concurrency control, row-level locks, CHECK constraints |
| **LLM Provider** | Groq API | Ultra-low latency inference with native tool calling |
| **LLM Model** | `llama-3.3-70b-versatile` (fallback: `llama-3.1-8b-instant`) | State-of-the-art tool-use reasoning and function calling |
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` | 384-dimensional dense vectors, executed locally on CPU/GPU |
| **Vector Index** | ChromaDB 1.5+ | Local persistent HNSW vector indexing with cosine distance |
| **Machine Learning** | `scikit-learn` 1.4+, `pandas` 3.0+, `numpy` 2.5+ | Direct multi-step gradient boosting and time-series feature engineering |
| **Testing** | `pytest` 9.1+, `pytest-django` 4.14+ | Comprehensive automated test execution |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS | High-performance dealer interface |

---

## 4. Repository Structure

```text
.
├── API_CONTRACT.md              # Exact API specification and grading rules
├── DECISIONS.md                 # Required 8 technical decisions with code citations
├── README.md                    # This documentation
├── VIKMO_DealerDesk_Assignment.pdf # Original assignment specification
├── manage.py                    # Django management script
├── requirements.txt             # Clean Python dependency manifest
├── pytest.ini                   # Pytest configuration
├── conftest.py                  # Pytest root configuration
├── smoke_test.py                # Official contract smoke test suite
├── .env.example                 # Sanitized environment template
├── core/                        # Main Django application
│   ├── models.py                # Relational schema (Product, Dealer, Order, etc.)
│   ├── views.py                 # API controllers and endpoints
│   ├── serializers.py           # DRF serializers and format validation
│   ├── exceptions.py            # Custom exception handler with contract error shape
│   ├── services/                # Business logic services
│   │   ├── order_service.py     # Order state machine, stock locks, GST
│   │   ├── inventory_service.py # Inventory update audit trail
│   │   ├── sequence_service.py  # Monotonic order numbering
│   │   └── supplier_sync_service.py # 2-stage supplier synchronization
│   ├── assistant/               # GenAI dealer assistant
│   │   ├── agent.py             # Groq tool-calling multi-turn loop
│   │   ├── tools.py             # search_parts, check_stock, create_draft_order
│   │   ├── vector_store.py      # ChromaDB HNSW indexing and hybrid retrieval
│   │   ├── embedding_service.py # SentenceTransformer local singleton
│   │   ├── guardrails.py        # Prompt injection filters and SKU validation
│   │   └── evaluate_retrieval.py# Empirical retrieval benchmark script
│   └── tests/                   # Core automated test suite
├── forecasting/                 # Demand forecasting module
│   ├── train.py                 # Model training and artifact generation
│   ├── backtest.py              # Chronological rolling-origin backtest
│   ├── features.py              # Anti-leakage feature engineering
│   ├── forecast_service.py      # /api/forecast/{sku}/ service
│   ├── reorder.py               # /api/reorder-suggestions/ safety stock math
│   └── tests/                   # Forecasting automated test suite
├── data/                        # Original CSV datasets (unmodified)
├── ml/
│   └── forecast.csv             # Committed 160-row forecast artifact
├── supplier_mock/               # Upstream supplier simulator for testing
└── frontend/                    # React 19 dealer portal
```

---

## 5. Clean-Checkout Setup & Run Instructions

### Step 1: Clone Repository
```bash
git clone https://github.com/Hariprasath1x/VIKMO-DealerDesk-Take-Home-Assignment.git
cd VIKMO-DealerDesk-Take-Home-Assignment
```

### Step 2: Environment Configuration
Copy the provided environment template:
```bash
cp .env.example .env
```
Edit `.env` to configure your PostgreSQL connection and LLM key:
```env
DATABASE_URL=postgres://postgres:postgres@localhost:5432/dealerdesk
GROQ_API_KEY=gsk_your_groq_api_key_here
DJANGO_SECRET_KEY=local-dev-secret-key
SUPPLIER_API_URL=http://127.0.0.1:8099
SUPPLIER_API_KEY=dev-supplier-key
```

### Step 3: Install Dependencies
Create and activate a virtual environment, then install requirements:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 4: Execute Grading Run Sequence
The system strictly fulfills the mandatory run contract:
```bash
python manage.py migrate --noinput
python manage.py seed_data
python manage.py seed_data
python manage.py runserver 0.0.0.0:8000 --noreload
```

> [!NOTE]
> `python manage.py seed_data` is completely idempotent. Running it repeatedly updates existing records without creating duplicates. It loads:
> - 600 catalogue products from `data/catalogue.csv`
> - 25 dealer accounts from `data/dealers.csv`
> - Synchronizes all 600 product vector embeddings into local ChromaDB storage.

---

## 6. API Endpoint Overview

All API responses use standard JSON with trailing slashes. All errors conform to the contract shape:
`{"error": {"code": "ERROR_CODE", "message": "Human readable text", "details": []}}`.

| Method | Path | Description | Key Query / Body Parameters |
|---|---|---|---|
| `GET` | `/api/health/` | Health check | Returns `200 {"status": "ok"}` |
| `GET` | `/api/products/` | Paginated product catalogue | `search`, `category`, `vehicle`, `page`, `page_size` |
| `POST` | `/api/products/` | Create new product (stock 0) | `sku`, `name`, `category`, `brand`, `vehicle_fitment`, `price` |
| `GET` | `/api/products/{sku}/` | Product detail with live stock | Returns 200 with product object or 404 |
| `PATCH` | `/api/products/{sku}/` | Partial product update | `price`, `description`, etc. (SKU immutable) |
| `PUT` | `/api/inventory/{sku}/` | Set live stock level | `{"quantity": 50, "reason": "stock count correction"}` |
| `GET` | `/api/dealers/` | Paginated dealer list | `page`, `page_size` |
| `POST` | `/api/dealers/` | Create dealer profile | `dealer_code`, `name`, `credit_limit`, `gstin`, `city` |
| `GET` | `/api/dealers/{id}/` | Dealer detail | Returns 200 with dealer object or 404 |
| `POST` | `/api/orders/` | Create DRAFT order | `{"dealer_id": 7, "items": [{"sku": "BRK-1044", "quantity": 2}]}` |
| `GET` | `/api/orders/` | Paginated orders list | `dealer_id`, `status`, `page`, `page_size` |
| `GET` | `/api/orders/{order_number}/` | Order detail with line GST | Returns full order object with itemized tax |
| `PUT` | `/api/orders/{order_number}/` | Replace items (DRAFT only) | `{"items": [{"sku": "FIL-1009", "quantity": 5}]}` |
| `POST` | `/api/orders/{order_number}/confirm/` | Confirm order & deduct stock | Atomic stock decrement; 409 if insufficient |
| `POST` | `/api/orders/{order_number}/dispatch/`| Dispatch confirmed order | `CONFIRMED` $\to$ `DISPATCHED` |
| `POST` | `/api/orders/{order_number}/deliver/` | Deliver dispatched order | `DISPATCHED` $\to$ `DELIVERED` (final) |
| `POST` | `/api/orders/{order_number}/cancel/`  | Cancel order & restore stock | Restores stock exactly once if previously CONFIRMED |
| `POST` | `/api/assistant/chat/` | AI Dealer Assistant | `{"session_id": "s1", "dealer_id": 7, "message": "..."}` |
| `GET` | `/api/forecast/{sku}/` | 4-week forecast for SKU | Returns 4 weeks of predictions from `ml/forecast.csv` |
| `GET` | `/api/reorder-suggestions/` | 40-SKU reorder suggestions | Safety stock, live stock, and $ROP$ recommendation |
| `POST` | `/api/sync/supplier/` | 2-stage supplier catalogue sync | Fetches pages, handles 429 backoff, reconciles catalogue |

---

## 7. AI Dealer Assistant (GenAI)

### Design & Operation
The assistant (`core/assistant/`) provides dealers with natural-language parts identification, stock queries, and draft order creation.

1. **Model Selection**: Groq API using `llama-3.3-70b-versatile` (with graceful `llama-3.1-8b-instant` fallback and local deterministic fallback if no API key is set).
2. **Local Vector Search**: Embedded using `sentence-transformers/all-MiniLM-L6-v2` locally and queried in ChromaDB using HNSW cosine distance. No catalogue text or queries are sent to external embedding APIs.
3. **Strict Live Grounding**: Product prices and stock levels are never stored in vectors. In `search_parts_vector`, candidate IDs retrieved from ChromaDB are immediately joined with live PostgreSQL records. In `check_stock`, the database is queried directly.
4. **Draft Orders Only**: The assistant only has access to `create_draft_order`. It can never confirm orders, modify prices, or bypass stock constraints.
5. **Session Isolation**: Conversation context is strictly scoped by `session_id` (`core/models.py:ChatSession`), preventing cross-dealer memory leakage.
6. **Prompt Injection Defense**:
   - `data/catalogue.csv` contains adversarial prompt injection attacks (`CHN-1037` attempting a 90% discount with `VIKMO-FREE-90`, and `BDY-1070` attempting unauthorized admin mode).
   - DealerDesk uses multi-tier defense:
     * **Input Sanitization**: `sanitize_untrusted_text()` scrubs known injection patterns prior to tool formatting.
     * **Data Delimitation**: Catalogue entries are isolated inside `<part_item>` XML tags, and system instructions command the model to treat content as passive data attributes.
     * **Output Redaction**: `post_process_reply()` strips unauthorized discount codes or override phrases.
     * **Structural Invariance**: The assistant lacks any mechanism to alter PostgreSQL pricing or bypass stock checks.

### Empirical Retrieval Benchmark
Evaluated via `python core/assistant/evaluate_retrieval.py`:
- **Positive Test Queries**: 8
- **Recall@1**: 50.0%
- **Recall@5**: 100.0%
- **Mean Reciprocal Rank (MRR)**: 0.7292
- **Out-of-Domain Rejection Rate**: 100.0% (irrelevant non-automotive queries rejected)

---

## 8. Demand Forecasting & Inventory Optimization (ML)

### Target Horizon & Artifact
- **Target SKUs**: 40 SKUs specified in `data/lead_times.csv`.
- **Target Forecast Weeks**: 4 weeks starting `2026-09-28`:
  1. `2026-09-28`
  2. `2026-10-05`
  3. `2026-10-12`
  4. `2026-10-19`
- **Committed File**: `ml/forecast.csv` (exactly 160 rows, schema: `sku,week_start,forecast_units`). Verified non-negative, zero missing values, zero duplicates.

### Modeling Methodology
- **Established SKUs (34 SKUs)**: Direct multi-step `GradientBoostingRegressor` (100 estimators, max depth 3) with 14 engineered features: autoregressive lags ($t-1, t-2, t-3, t-4, t-52$), rolling statistics (4-week and 12-week mean/std), upcoming promotional indicator (`promo_future`), and signed calendar distance to Diwali (`weeks_to_diwali`).
- **Intermittent SKUs (4 SKUs with >40% zero demand)**: Robust 12-week trimmed average and Croston-style smoothing.
- **New SKUs (2 SKUs with only 6 weeks history)**: Exponential moving average smoothing scaled by promotional lift multipliers.
- **Anti-Leakage Guarantee**: All feature extraction enforces strict chronological cutoffs (`week_start <= origin_week` at `forecasting/features.py:73` and `forecasting/backtest.py:113`).

### Chronological Rolling-Origin Backtest Results
Validated over 4 cutoff folds (W-16, W-12, W-8, W-4) using `python -m forecasting.backtest`:

| Model / Strategy | WAPE | MAE | RMSE | Performance vs Best Baseline |
|---|---|---|---|---|
| Baseline 1: Last Observed Value | 38.45% | 13.28 | 20.44 | +8.71% WAPE |
| Baseline 2: Recent 4-Week Average | 29.74% | 10.27 | 15.74 | Reference best baseline |
| Baseline 3: Same Week Last Year | 34.28% | 11.84 | 18.14 | +4.54% WAPE |
| **Candidate: Segmented GBDT Hybrid** | **27.96%** | **9.66** | **14.98** | **Beats all baselines (-1.78% WAPE, -6.0% relative error reduction)** |

### Safety Stock & Reorder Suggestions Formula
Implemented strictly according to `API_CONTRACT.md` §10 in `forecasting/reorder.py`:
- $L$: `lead_time_weeks` from `data/lead_times.csv`
- $\text{lead\_time\_demand} = \sum_{w=1}^{L} \text{forecast\_units}_w$
- $\sigma$: Sample standard deviation ($ddof=1$) over the last 12 weeks of `sales_history.csv`
- $\text{safety\_stock} = \lceil 1.65 \times \sigma \times \sqrt{L} \rceil$
- $\text{reorder\_point} = \text{lead\_time\_demand} + \text{safety\_stock}$
- $\text{reorder\_qty} = \max(0, \lceil \text{reorder\_point} - \text{current\_stock} \rceil)$ using live stock from PostgreSQL.

---

## 9. Automated Testing & Verification

### Run the Full Verification Suite
```bash
# 1. Dependency integrity check
python -m pip check

# 2. Django system checks & migration drift
python manage.py check
python manage.py makemigrations --check --dry-run

# 3. Backend automated tests (both commands run the verified 62-test suite)
python -m pytest -v
python manage.py test --noinput

# 4. Chronological backtest benchmark
python -m forecasting.backtest

# 5. Contract smoke test against running server
python smoke_test.py --base-url http://localhost:8000 --track aiml
```

### Verified Test Results Summary
- **Python Pip Check**: Clean (0 broken requirements).
- **Django System Check**: 0 issues identified.
- **Migration Drift**: No changes detected.
- **Test Suite**: **62/62 tests passed** (100% pass rate).
- **Smoke Test (`--track aiml`)**: **10/10 checks passed**.
- **Frontend Build (`npm run build`)**: Clean build, 0 errors.

---

## 10. Frontend Dealer Portal (`frontend/`)

A production-ready dealer interface built on React 19, TypeScript, and Vite:

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Key views include:
- **Dashboard**: Dealer credit profile, live inventory summary, quick action shortcuts.
- **Catalogue**: Search with vehicle fitment and category filters, live stock indicators, quick cart additions.
- **Order Desk**: Itemized draft orders, live 18% GST line breakdowns, atomic status transitions.
- **AI Parts Assistant**: Interactive chat interface displaying tool-calling execution cards, cited SKUs, and live inventory grounding.
- **Forecasting & Reordering**: 4-week demand charts and instant safety-stock reorder suggestions.

To produce a production distribution:
```bash
npm run build
```

---

## 11. Walkthrough Video Recording Outline

> [!NOTE]
> **Video Deliverable Status**: Manual recording deliverable.
> As an automated agent without a screen capture interface or audio microphone, I have prepared the structured 5-minute video presentation script and code walkthrough path below. When recorded by the candidate, insert the unlisted YouTube/Loom/Drive link here: `[Insert unlisted video link here]`.

### 5-Minute Technical Presentation Outline (AI/ML Track)
1. **Minute 1: Relational Schema & Fresh-Start Contract**
   - Open [`core/models.py`](core/models.py#L6-L135).
   - Walk through `Product`, `Dealer`, `Order`, and `OrderItem`.
   - Explain why `on_delete=models.PROTECT` is enforced on `Order.dealer` and `OrderItem.product` to preserve financial auditability and statutory GST history.
   - Highlight the non-negative check constraints on stock and line item quantities.
2. **Minute 2: AI Dealer Assistant Architecture & Tool-Calling Loop**
   - Open [`core/assistant/agent.py`](core/assistant/agent.py#L37-L199) and [`core/assistant/tools.py`](core/assistant/tools.py#L9-L91).
   - Trace the request flow for `POST /api/assistant/chat/` from user query to Groq LLM tool calling.
   - Show how the model invokes `search_parts` and `check_stock`, and how tool outputs are fed back into the conversation.
3. **Minute 3: Live Grounding & Prompt Injection Defense**
   - Open [`core/assistant/vector_store.py`](core/assistant/vector_store.py#L177-L208) and [`core/assistant/guardrails.py`](core/assistant/guardrails.py#L15-L86).
   - Demonstrate that ChromaDB vectors do not contain prices or stock; candidate IDs are joined with PostgreSQL at request time.
   - Point out real adversarial attacks in `data/catalogue.csv` (`CHN-1037` 90% discount, `BDY-1070` admin mode) and show how regex sanitization, XML bounding, and draft-order-only sandboxing nullify them.
4. **Minute 4: Demand Forecasting, Anti-Leakage & Backtest Metrics**
   - Open [`forecasting/train.py`](forecasting/train.py#L1-L127) and [`forecasting/features.py`](forecasting/features.py#L70-L88).
   - Highlight the anti-leakage line [`forecasting/features.py:73`](forecasting/features.py#L73) restricting data to `week_start <= origin_week`.
   - Explain the 3-tier strategy (established GBDT, intermittent trimmed mean, new SKU exponential smoothing).
   - Show the terminal output of `python -m forecasting.backtest` proving the 27.96% WAPE beating all 3 baselines.
5. **Minute 5: Safety Stock Calculation & Portal Demonstration**
   - Open [`forecasting/reorder.py`](forecasting/reorder.py#L15-L75).
   - Walk through the exact formula for lead-time demand, sample standard deviation $\sigma$, safety stock, and live stock subtraction.
   - Quick visual tour of the React portal (`frontend/`) showing the AI chat and reorder views operating against the live Django API.

---

## 12. Known Limitations & Assumptions

1. **External LLM Service**: The assistant requires internet connectivity to reach the Groq API endpoint (`https://api.groq.com/openai/v1`). If `GROQ_API_KEY` is not provided or the network is blocked, a deterministic rule-guided fallback agent handles queries and executes tools safely.
2. **Local Embedding Warmup**: On cold starts, `sentence-transformers/all-MiniLM-L6-v2` takes ~1.5s to load weights into memory on first invocation. Subsequent calls execute in under 10ms.
3. **Asia/Kolkata Timezone**: The project uses `Asia/Kolkata` as configured in `dealerdesk/settings.py` for date partitioning of daily order numbers (`ORD-YYYYMMDD-NNNN`).
