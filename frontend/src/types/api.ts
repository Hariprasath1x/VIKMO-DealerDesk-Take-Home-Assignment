export interface Product {
  sku: string;
  name: string;
  category: string;
  brand: string;
  vehicle_fitment: string;
  price: string;
  stock: number;
  description: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Dealer {
  id: number;
  dealer_code: string;
  name: string;
  city: string;
  phone: string;
  email: string;
  gstin: string;
  credit_limit: string;
}

export interface OrderItem {
  sku: string;
  name: string;
  quantity: number;
  unit_price: string;
  line_subtotal: string;
  line_tax: string;
  line_total: string;
}

export type OrderStatus = "DRAFT" | "CONFIRMED" | "DISPATCHED" | "DELIVERED" | "CANCELLED";

export interface Order {
  order_number: string;
  dealer_id: number;
  status: OrderStatus;
  items: OrderItem[];
  subtotal: string;
  tax_total: string;
  grand_total: string;
  created_at: string;
  updated_at: string;
}

export interface AssistantToolCall {
  name: string;
  arguments: Record<string, unknown>;
}

export interface AssistantChatResponse {
  reply: string;
  cited_skus: string[];
  tool_calls: AssistantToolCall[];
  actions: unknown[];
}

export interface ForecastWeek {
  week_start: string;
  forecast_units: number;
}

export interface ForecastDetail {
  sku: string;
  weeks: ForecastWeek[];
}

export interface ReorderSuggestion {
  sku: string;
  name: string;
  current_stock: number;
  lead_time_weeks: number;
  lead_time_demand: number;
  safety_stock: number;
  reorder_point: number;
  reorder_quantity: number;
  status: "SUFFICIENT" | "REORDER_NEEDED";
}

export interface SupplierSyncResponse {
  created: number;
  updated: number;
  unchanged: number;
  rejected: Array<{ supplier_sku: string; reason: string }>;
  pages_fetched: number;
  requests_made: number;
}

export interface ContractAPIError {
  error: {
    code: string;
    message: string;
    details: string[] | Array<{ sku: string; requested: number; available: number }> | unknown[];
  };
}
