# VIKMO DealerDesk — React Dealer Portal (Phase 7)

A responsive, production-minded B2B automotive dealer portal built with React, TypeScript, Vite, Tailwind CSS, and Recharts. Communicates exclusively with the DealerDesk Django REST API (`http://127.0.0.1:8000`).

---

## 🚀 Features & Screens

1. **Dealer Dashboard (`#dashboard`)**:
   - Live KPI cards: Total Catalogue Products, Low Stock Alerts (<10 units), Active Orders, Priority Reorder Alerts.
   - Priority Reorder recommendations preview with Lead-Time Demand and Safety Stock.
   - Recent Purchase Orders table with status pills and grand totals (including 18% GST).
   - Quick triggers for Supplier Catalogue Sync.

2. **Parts Catalogue (`#catalogue`)**:
   - Backend search and multi-facet filtering (Category: Engine, Brakes, Transmission, etc.; Vehicle Fitment: Maruti, Hyundai, Tata, etc.).
   - Paginated product grid displaying SKU, Brand, Category, Vehicle Compatibility, Dealer Unit Price, and Real-Time Stock Status.
   - **Product Detail Modal**: Full technical descriptions and instant Inventory Stock Adjustment (`PUT /api/inventory/{sku}/`).
   - **Draft Order Modal**: Select quantity, estimate 18% GST and totals in real-time, and create purchase orders (`POST /api/orders/`).

3. **Order Management (`#orders`)**:
   - Tab-based filtering across order lifecycle states (`DRAFT`, `CONFIRMED`, `DISPATCHED`, `DELIVERED`, `CANCELLED`).
   - Order details modal with line-item breakdown (SKU, quantity, unit price, 18% GST tax, line totals).
   - Atomic state transitions with confirmation dialogs:
     - `Confirm Order`: Atomically deducts inventory using PostgreSQL row locking. Displays structured `INSUFFICIENT_STOCK` error cards if stock is unavailable.
     - `Cancel Order`: Restores previously reserved stock back into inventory.
     - `Dispatch Order` & `Deliver Order`: Complete fulfillment transitions.

4. **AI Dealer Assistant (`#assistant`)**:
   - Conversational assistant powered by Groq (`openai/gpt-oss-120b`) and local dense RAG embeddings (ChromaDB + Sentence Transformers).
   - Persistent conversation session ID across messages (with "New Session" reset button).
   - Collapsible tool-call execution timeline cards showing agent actions (`search_parts`, `check_stock`, `create_draft_order`).
   - Interactive cited SKU chips with direct catalogue navigation.
   - Zero exposure of internal API keys or tracebacks to the client.

5. **Demand Forecast & Reorder Intelligence (`#forecast`)**:
   - Four-week unit demand chart powered by Recharts (`/api/forecast/{sku}/`) based on GBDT machine-learning models.
   - Advisory banner clarifying that demand forecasts are planning estimates, not guaranteed sales.
   - Live stock vs Reorder Point ($ROP = d \times L + SS$) comparison table (`/api/reorder-suggestions/`).
   - Filter for products needing urgent attention (`REORDER_NEEDED`).
   - "Draft Reorder" action to instantly place draft orders for the recommended reorder quantity.

---

## 🛠️ Stack & Architecture

- **Framework**: React 19 + TypeScript + Vite 8
- **Styling**: Tailwind CSS v4 with custom design tokens & responsive sidebar layout
- **Charts**: Recharts (`ResponsiveContainer`, `BarChart`, `CartesianGrid`, `Tooltip`, `Legend`)
- **Icons**: Lucide React
- **API Client**: Strongly typed fetch client (`src/lib/api.ts`) adhering to the exact `API_CONTRACT.md` schemas
- **No 2nd Backend**: Vite dev server proxies `/api` directly to `http://127.0.0.1:8000`

---

## 📦 Setup & Development

### 1. Prerequisites
Ensure the Django API server is running on `http://127.0.0.1:8000`:
```bash
python manage.py runserver 0.0.0.0:8000
```

### 2. Install Dependencies
```bash
cd frontend
npm install
```

### 3. Run Dev Server
```bash
npm run dev
```
The portal is available at `http://localhost:5173`.

### 4. Build for Production
```bash
npm run build
```
Generates minified, production-optimized assets in `frontend/dist/`.

---

## ⚙️ Environment Variables

Optional: create `frontend/.env` to override the backend API base URL:
```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```
*(If unset, the application uses relative `/api` paths with Vite proxying during dev)*.
