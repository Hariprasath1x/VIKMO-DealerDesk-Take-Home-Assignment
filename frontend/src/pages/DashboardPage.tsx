import React, { useEffect, useState } from "react";
import {
  Boxes,
  ShoppingCart,
  AlertTriangle,
  TrendingUp,
  ArrowRight,
  RefreshCw,
  Clock,
  Sparkles,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Alert } from "../components/ui/Alert";
import { getProducts, getOrders, getReorderSuggestions } from "../lib/api";
import type { Order, ReorderSuggestion } from "../types/api";
import { formatCurrency, formatDate } from "../lib/utils";
import type { ActiveTab } from "../components/Layout";

interface DashboardPageProps {
  onNavigate: (tab: ActiveTab) => void;
  onOpenSync: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate, onOpenSync }) => {
  const [totalProducts, setTotalProducts] = useState<number | null>(null);
  const [recentOrders, setRecentOrders] = useState<Order[]>([]);
  const [reorderItems, setReorderItems] = useState<ReorderSuggestion[]>([]);
  const [lowStockCount, setLowStockCount] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Fetch overview data from existing endpoints concurrently
      const [prodRes, orderRes, reorderRes] = await Promise.all([
        getProducts({ page_size: 10 }),
        getOrders({ page_size: 5 }),
        getReorderSuggestions(),
      ]);

      setTotalProducts(prodRes.count);
      setRecentOrders(orderRes.results);

      const itemsNeedingReorder = reorderRes.results.filter(
        (r) => r.status === "REORDER_NEEDED"
      );
      setReorderItems(itemsNeedingReorder);

      // Count low stock in recent sample or items needing reorder
      const lowStock = reorderRes.results.filter((r) => r.current_stock < 10).length;
      setLowStockCount(lowStock);
    } catch (err: unknown) {
      console.error("Dashboard data load failed:", err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Could not load dashboard data from backend.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const getStatusBadge = (status: Order["status"]) => {
    switch (status) {
      case "CONFIRMED":
        return <Badge variant="info">CONFIRMED</Badge>;
      case "DISPATCHED":
        return <Badge variant="default">DISPATCHED</Badge>;
      case "DELIVERED":
        return <Badge variant="success">DELIVERED</Badge>;
      case "CANCELLED":
        return <Badge variant="destructive">CANCELLED</Badge>;
      case "DRAFT":
      default:
        return <Badge variant="secondary">DRAFT</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Welcome */}
      <div className="bg-linear-to-r from-blue-700 via-blue-800 to-indigo-900 rounded-2xl p-6 sm:p-8 text-white shadow-md relative overflow-hidden">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-white/10 backdrop-blur-xs text-xs font-medium text-blue-100 mb-3 border border-white/10">
            <Sparkles className="w-3.5 h-3.5 text-blue-300" />
            AI-Enhanced Dealer Operations
          </div>
          <h2 className="text-2xl sm:text-3xl font-extrabold tracking-tight">
            Automotive Parts & Inventory Center
          </h2>
          <p className="mt-2 text-sm sm:text-base text-blue-100/90 leading-relaxed">
            Monitor real-time parts availability, dispatch orders with atomic GST calculations, and
            leverage GBDT demand forecasts to prevent stockouts.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onNavigate("catalogue")}
              className="gap-2 bg-white text-blue-900 hover:bg-blue-50 font-semibold"
            >
              <Boxes className="w-4 h-4" />
              Browse Catalogue
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate("assistant")}
              className="gap-2 text-white border-white/30 hover:bg-white/10"
            >
              <Sparkles className="w-4 h-4 text-blue-300" />
              Ask AI Assistant
            </Button>
          </div>
        </div>
      </div>

      {error && (
        <Alert variant="destructive" title="API Connection Notice">
          {error}
        </Alert>
      )}

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* KPI 1: Catalogue Products */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Catalogue Items
            </CardTitle>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center dark:bg-blue-900/30 dark:text-blue-400">
              <Boxes className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {isLoading ? "..." : totalProducts ?? "—"}
            </div>
            <p className="text-xs text-slate-500 mt-1">Active automotive SKUs</p>
          </CardContent>
        </Card>

        {/* KPI 2: Critical Stock Alerts */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Low Stock Alerts
            </CardTitle>
            <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center dark:bg-rose-900/30 dark:text-rose-400">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-rose-600">
              {isLoading ? "..." : lowStockCount}
            </div>
            <p className="text-xs text-slate-500 mt-1">SKUs with &lt; 10 units in stock</p>
          </CardContent>
        </Card>

        {/* KPI 3: Reorder Needed */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Reorders Needed
            </CardTitle>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center dark:bg-amber-900/30 dark:text-amber-400">
              <TrendingUp className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {isLoading ? "..." : reorderItems.length}
            </div>
            <p className="text-xs text-slate-500 mt-1">Stock below safety reorder point</p>
          </CardContent>
        </Card>

        {/* KPI 4: Recent Orders */}
        <Card className="hover:shadow-md transition-shadow">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
              Active Orders
            </CardTitle>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center dark:bg-emerald-900/30 dark:text-emerald-400">
              <ShoppingCart className="w-4 h-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
              {isLoading ? "..." : recentOrders.length}
            </div>
            <p className="text-xs text-slate-500 mt-1">Recent dealer purchase orders</p>
          </CardContent>
        </Card>
      </div>

      {/* Two-Column Work Section: Reorder Alerts & Recent Orders */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Reorder Recommendations Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <CardTitle className="text-base font-semibold">Priority Reorder Alerts</CardTitle>
              <p className="text-xs text-slate-500 mt-0.5">
                Calculated using lead-time demand + safety stock
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate("forecast")}
              className="text-xs text-blue-600 gap-1"
            >
              View All <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-8 text-center text-sm text-slate-400">Loading alerts...</div>
            ) : reorderItems.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-500">
                All modeled inventory levels are currently above reorder points.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {reorderItems.slice(0, 4).map((item) => (
                  <div key={item.sku} className="py-3 flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-200">
                          {item.sku}
                        </span>
                        <Badge variant="warning" className="text-[10px]">
                          Stock: {item.current_stock}
                        </Badge>
                      </div>
                      <p className="text-xs text-slate-500 truncate max-w-[220px] sm:max-w-xs mt-0.5">
                        {item.name}
                      </p>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                        ROP: {item.reorder_point} units
                      </div>
                      <span className="text-[11px] font-medium text-amber-600 dark:text-amber-400">
                        Order +{item.reorder_quantity}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Orders Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <CardTitle className="text-base font-semibold">Recent Purchase Orders</CardTitle>
              <p className="text-xs text-slate-500 mt-0.5">
                Lifecycle status and confirmed totals
              </p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onNavigate("orders")}
              className="text-xs text-blue-600 gap-1"
            >
              All Orders <ArrowRight className="w-3.5 h-3.5" />
            </Button>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-8 text-center text-sm text-slate-400">Loading orders...</div>
            ) : recentOrders.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-500">
                No orders placed yet. Browse the catalogue or ask the AI Assistant.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {recentOrders.map((order) => (
                  <div
                    key={order.order_number}
                    className="py-3 flex items-center justify-between cursor-pointer hover:bg-slate-50/50 rounded-lg px-2 -mx-2 transition-colors dark:hover:bg-slate-800/40"
                    onClick={() => onNavigate("orders")}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-slate-900 dark:text-slate-100">
                          {order.order_number}
                        </span>
                        {getStatusBadge(order.status)}
                      </div>
                      <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
                        <Clock className="w-3 h-3" />
                        <span>{formatDate(order.created_at)}</span>
                        <span>•</span>
                        <span>{order.items.length} items</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                        {formatCurrency(order.grand_total)}
                      </div>
                      <span className="text-[10px] text-slate-400">Incl. GST</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Quick Action Shortcuts Banner */}
      <div className="bg-slate-100/70 border border-slate-200 rounded-xl p-5 dark:bg-slate-800/50 dark:border-slate-800 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-600/10 text-blue-600 flex items-center justify-center shrink-0">
            <RefreshCw className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Supplier Catalogue Synchronization
            </h4>
            <p className="text-xs text-slate-500 mt-0.5">
              Pull updated product listings from upstream supplier mock with 2-stage atomic safety.
            </p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={onOpenSync} className="whitespace-nowrap gap-2">
          <RefreshCw className="w-3.5 h-3.5" />
          Sync Catalogue Now
        </Button>
      </div>
    </div>
  );
};
