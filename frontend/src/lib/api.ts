import type {
  Product,
  PaginatedResponse,
  Dealer,
  Order,
  AssistantChatResponse,
  ForecastDetail,
  ReorderSuggestion,
  SupplierSyncResponse,
  ContractAPIError,
} from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export class APIClientError extends Error {
  public code: string;
  public details: unknown[];
  public status: number;

  constructor(status: number, errorData: ContractAPIError["error"]) {
    super(errorData.message || "An API error occurred");
    this.name = "APIClientError";
    this.status = status;
    this.code = errorData.code || "API_ERROR";
    this.details = Array.isArray(errorData.details) ? errorData.details : [];
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && typeof options.body === "string") {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorJson: ContractAPIError = {
      error: { code: "HTTP_ERROR", message: response.statusText, details: [] },
    };
    try {
      errorJson = await response.json();
    } catch {
      // fallback if non-json response
    }
    throw new APIClientError(response.status, errorJson.error);
  }

  return response.json() as Promise<T>;
}

// -------------------------------------------------------------
// Products & Inventory
// -------------------------------------------------------------
export async function getProducts(params?: {
  search?: string;
  category?: string;
  vehicle?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Product>> {
  const query = new URLSearchParams();
  if (params?.search) query.set("search", params.search);
  if (params?.category) query.set("category", params.category);
  if (params?.vehicle) query.set("vehicle", params.vehicle);
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());

  const qs = query.toString();
  return request<PaginatedResponse<Product>>(`/api/products/${qs ? `?${qs}` : ""}`);
}

export async function getProduct(sku: string): Promise<Product> {
  return request<Product>(`/api/products/${encodeURIComponent(sku)}/`);
}

export async function updateInventory(sku: string, quantity: number, reason?: string) {
  return request<{ sku: string; quantity: number }>(`/api/inventory/${encodeURIComponent(sku)}/`, {
    method: "PUT",
    body: JSON.stringify({ quantity, reason: reason || "Manual dashboard update" }),
  });
}

// -------------------------------------------------------------
// Dealers
// -------------------------------------------------------------
export async function getDealers(page = 1, pageSize = 50): Promise<PaginatedResponse<Dealer>> {
  return request<PaginatedResponse<Dealer>>(`/api/dealers/?page=${page}&page_size=${pageSize}`);
}

// -------------------------------------------------------------
// Orders & Transitions
// -------------------------------------------------------------
export async function getOrders(params?: {
  dealer_id?: number;
  status?: string;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<Order>> {
  const query = new URLSearchParams();
  if (params?.dealer_id) query.set("dealer_id", params.dealer_id.toString());
  if (params?.status) query.set("status", params.status);
  if (params?.page) query.set("page", params.page.toString());
  if (params?.page_size) query.set("page_size", params.page_size.toString());

  const qs = query.toString();
  return request<PaginatedResponse<Order>>(`/api/orders/${qs ? `?${qs}` : ""}`);
}

export async function getOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/`);
}

export async function createDraftOrder(
  dealerId: number,
  items: Array<{ sku: string; quantity: number }>,
  idempotencyKey?: string
): Promise<Order> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }
  return request<Order>("/api/orders/", {
    method: "POST",
    headers,
    body: JSON.stringify({ dealer_id: dealerId, items }),
  });
}

export async function updateDraftOrder(
  orderNumber: string,
  items: Array<{ sku: string; quantity: number }>
): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/`, {
    method: "PUT",
    body: JSON.stringify({ items }),
  });
}

export async function confirmOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/confirm/`, {
    method: "POST",
  });
}

export async function dispatchOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/dispatch/`, {
    method: "POST",
  });
}

export async function deliverOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/deliver/`, {
    method: "POST",
  });
}

export async function cancelOrder(orderNumber: string): Promise<Order> {
  return request<Order>(`/api/orders/${encodeURIComponent(orderNumber)}/cancel/`, {
    method: "POST",
  });
}

// -------------------------------------------------------------
// Assistant
// -------------------------------------------------------------
export async function sendAssistantChat(
  sessionId: string,
  dealerId: number,
  message: string
): Promise<AssistantChatResponse> {
  return request<AssistantChatResponse>("/api/assistant/chat/", {
    method: "POST",
    body: JSON.stringify({
      session_id: sessionId,
      dealer_id: dealerId,
      message,
    }),
  });
}

// -------------------------------------------------------------
// Forecast & Reorder
// -------------------------------------------------------------
export async function getForecast(sku: string): Promise<ForecastDetail> {
  return request<ForecastDetail>(`/api/forecast/${encodeURIComponent(sku)}/`);
}

export async function getReorderSuggestions(): Promise<{ results: ReorderSuggestion[] }> {
  return request<{ results: ReorderSuggestion[] }>("/api/reorder-suggestions/");
}

// -------------------------------------------------------------
// Supplier Sync
// -------------------------------------------------------------
export async function triggerSupplierSync(): Promise<SupplierSyncResponse> {
  return request<SupplierSyncResponse>("/api/sync/supplier/", {
    method: "POST",
  });
}
