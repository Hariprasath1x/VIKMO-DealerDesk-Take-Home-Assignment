import React, { useEffect, useState } from "react";
import {
  Calendar,
  ShoppingCart,
  CheckCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import { Card, CardHeader, CardTitle, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Select } from "../components/ui/Select";
import { Modal } from "../components/ui/Modal";
import { Alert } from "../components/ui/Alert";
import { Input } from "../components/ui/Input";
import { getForecast, getReorderSuggestions, createDraftOrder } from "../lib/api";
import type { ForecastDetail, ReorderSuggestion, Order } from "../types/api";
import { formatWeekDate } from "../lib/utils";
import { useDealer } from "../context/DealerContext";
import type { ActiveTab } from "../components/Layout";

interface ForecastPageProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const ForecastPage: React.FC<ForecastPageProps> = ({ onNavigate }) => {
  const { currentDealer } = useDealer();

  const [suggestions, setSuggestions] = useState<ReorderSuggestion[]>([]);
  const [filterNeedsReorderOnly, setFilterNeedsReorderOnly] = useState<boolean>(true);
  const [selectedSku, setSelectedSku] = useState<string>("");
  const [forecastDetail, setForecastDetail] = useState<ForecastDetail | null>(null);

  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState<boolean>(true);
  const [isLoadingForecast, setIsLoadingForecast] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Quick Order Modal from Reorder suggestion
  const [orderModalItem, setOrderModalItem] = useState<ReorderSuggestion | null>(null);
  const [orderQty, setOrderQty] = useState<number>(1);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState<boolean>(false);
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);

  // 1. Fetch all reorder suggestions
  useEffect(() => {
    const fetchSuggestions = async () => {
      try {
        setIsLoadingSuggestions(true);
        setError(null);
        const res = await getReorderSuggestions();
        setSuggestions(res.results);

        // Default to first item needing reorder or first available SKU
        if (res.results.length > 0) {
          const firstNeeded = res.results.find((r) => r.status === "REORDER_NEEDED");
          const defaultSku = firstNeeded ? firstNeeded.sku : res.results[0].sku;
          setSelectedSku(defaultSku);
        }
      } catch (err: unknown) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError("Failed to fetch reorder suggestions.");
        }
      } finally {
        setIsLoadingSuggestions(false);
      }
    };

    fetchSuggestions();
  }, []);

  // 2. Fetch forecast data when selectedSku changes
  useEffect(() => {
    if (!selectedSku) return;

    const fetchSkuForecast = async () => {
      try {
        setIsLoadingForecast(true);
        const res = await getForecast(selectedSku);
        setForecastDetail(res);
      } catch (err: unknown) {
        console.error("Forecast fetch error:", err);
      } finally {
        setIsLoadingForecast(false);
      }
    };

    fetchSkuForecast();
  }, [selectedSku]);

  const handleOpenDraftOrder = (item: ReorderSuggestion) => {
    setOrderModalItem(item);
    setOrderQty(item.reorder_quantity > 0 ? item.reorder_quantity : 10);
    setCreatedOrder(null);
    setOrderError(null);
  };

  const handleConfirmDraftOrder = async () => {
    if (!orderModalItem || !currentDealer) return;
    try {
      setIsSubmittingOrder(true);
      setOrderError(null);
      const res = await createDraftOrder(currentDealer.id, [
        { sku: orderModalItem.sku, quantity: orderQty },
      ]);
      setCreatedOrder(res);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setOrderError(err.message);
      } else {
        setOrderError("Failed to create reorder draft.");
      }
    } finally {
      setIsSubmittingOrder(false);
    }
  };

  const displayedSuggestions = filterNeedsReorderOnly
    ? suggestions.filter((s) => s.status === "REORDER_NEEDED")
    : suggestions;

  const currentSelectedItem = suggestions.find((s) => s.sku === selectedSku);

  // Format forecast weeks for chart
  const chartData =
    forecastDetail?.weeks.map((w) => ({
      week: formatWeekDate(w.week_start),
      forecast_units: Math.round(w.forecast_units),
    })) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
          Demand Forecast & Reorder Intelligence
        </h2>
        <p className="text-xs text-slate-500 mt-0.5">
          GBDT machine learning forecasts with lead-time safety stock calculations
        </p>
      </div>

      {/* Advisory Banner */}
      <Alert variant="info" title="Forecast Planning Advisory">
        Four-week demand forecasts are generated by machine learning models trained on historical
        sales, promotional calendars, and holiday shifts. All figures are probabilistic estimates
        to guide inventory replenishments, not guaranteed demand commitments.
      </Alert>

      {error && (
        <Alert variant="destructive" title="Intelligence Service Error">
          {error}
        </Alert>
      )}

      {/* Top Section: Four-Week Demand Chart Card */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4 text-blue-600" />
              <CardTitle className="text-base font-semibold">
                Four-Week Predicted Unit Demand
              </CardTitle>
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              Weekly forecast volume starting September 28, 2026
            </p>
          </div>

          {/* SKU Picker Dropdown */}
          <div className="w-full sm:w-72">
            <label className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
              Select Modeled SKU:
            </label>
            <Select
              aria-label="Select Modeled SKU"
              value={selectedSku}
              onChange={(e) => setSelectedSku(e.target.value)}
              disabled={isLoadingSuggestions}
            >
              {suggestions.map((s) => (
                <option key={s.sku} value={s.sku}>
                  {s.sku} - {s.name.substring(0, 24)}...
                </option>
              ))}
            </Select>
          </div>
        </CardHeader>

        <CardContent>
          {/* Active SKU Meta Strip */}
          {currentSelectedItem && (
            <div className="mb-6 grid grid-cols-2 sm:grid-cols-4 gap-3 p-3 bg-slate-50 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800 text-xs">
              <div>
                <span className="text-slate-400 block text-[11px]">Current Stock:</span>
                <span className="font-bold text-slate-800 dark:text-slate-100">
                  {currentSelectedItem.current_stock} units
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Lead Time (L):</span>
                <span className="font-bold text-slate-800 dark:text-slate-100">
                  {currentSelectedItem.lead_time_weeks} weeks
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Reorder Point (ROP):</span>
                <span className="font-bold text-slate-800 dark:text-slate-100">
                  {currentSelectedItem.reorder_point} units
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-[11px]">Recommended Reorder:</span>
                <span
                  className={`font-bold ${
                    currentSelectedItem.reorder_quantity > 0
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-emerald-600 dark:text-emerald-400"
                  }`}
                >
                  +{currentSelectedItem.reorder_quantity} units
                </span>
              </div>
            </div>
          )}

          {/* Chart Graphic */}
          {isLoadingForecast ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-400">
              Loading 4-week forecast from backend...
            </div>
          ) : chartData.length === 0 ? (
            <div className="h-64 flex items-center justify-center text-xs text-slate-400">
              No forecast records found for selected SKU.
            </div>
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 10, right: 20, left: -10, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                  <XAxis dataKey="week" stroke="#64748b" fontSize={12} tickLine={false} />
                  <YAxis stroke="#64748b" fontSize={12} tickLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#0f172a",
                      borderColor: "#1e293b",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "12px",
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "8px" }} />
                  <Bar
                    dataKey="forecast_units"
                    name="Predicted Unit Demand"
                    fill="#2563eb"
                    radius={[6, 6, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Bottom Section: Reorder Recommendations Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4">
          <div>
            <CardTitle className="text-base font-semibold">
              Live Stock vs Reorder Point Intelligence
            </CardTitle>
            <p className="text-xs text-slate-500 mt-0.5">
              Formula: ROP = Lead Time Demand (d × L) + Safety Stock (SS); Reorder Q = max(0, ROP - stock)
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterNeedsReorderOnly(true)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                filterNeedsReorderOnly
                  ? "bg-amber-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              Needs Reorder Only ({suggestions.filter((s) => s.status === "REORDER_NEEDED").length})
            </button>
            <button
              onClick={() => setFilterNeedsReorderOnly(false)}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors cursor-pointer ${
                !filterNeedsReorderOnly
                  ? "bg-blue-600 text-white shadow-xs"
                  : "bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300"
              }`}
            >
              All Modeled SKUs ({suggestions.length})
            </button>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoadingSuggestions ? (
            <div className="py-16 text-center text-xs text-slate-400">
              Loading reorder metrics...
            </div>
          ) : displayedSuggestions.length === 0 ? (
            <div className="py-16 text-center text-xs text-slate-500">
              No products found for the selected filter.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 dark:border-slate-800 dark:bg-slate-800/50">
                    <th className="py-3 px-4 font-semibold">SKU & Part</th>
                    <th className="py-3 px-4 font-semibold text-center">Lead Time (L)</th>
                    <th className="py-3 px-4 font-semibold text-right">LT Demand</th>
                    <th className="py-3 px-4 font-semibold text-right">Safety Stock</th>
                    <th className="py-3 px-4 font-semibold text-right">Reorder Point</th>
                    <th className="py-3 px-4 font-semibold text-right">Current Stock</th>
                    <th className="py-3 px-4 font-semibold text-center">Status</th>
                    <th className="py-3 px-4 font-semibold text-right">Reorder Qty</th>
                    <th className="py-3 px-4 font-semibold text-center">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {displayedSuggestions.map((item) => {
                    const isSelected = item.sku === selectedSku;
                    return (
                      <tr
                        key={item.sku}
                        className={`hover:bg-slate-50/60 transition-colors dark:hover:bg-slate-800/30 ${
                          isSelected ? "bg-blue-50/40 dark:bg-blue-950/20" : ""
                        }`}
                      >
                        <td className="py-3 px-4">
                          <button
                            type="button"
                            onClick={() => setSelectedSku(item.sku)}
                            className="font-mono font-bold text-blue-600 hover:underline block text-left cursor-pointer dark:text-blue-400"
                          >
                            {item.sku}
                          </button>
                          <span className="text-slate-600 dark:text-slate-400 truncate max-w-[200px] block text-[11px]">
                            {item.name}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center font-medium">
                          {item.lead_time_weeks} wks
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-700 dark:text-slate-300">
                          {item.lead_time_demand}
                        </td>
                        <td className="py-3 px-4 text-right font-medium text-slate-700 dark:text-slate-300">
                          {item.safety_stock}
                        </td>
                        <td className="py-3 px-4 text-right font-bold text-slate-900 dark:text-slate-100">
                          {item.reorder_point}
                        </td>
                        <td className="py-3 px-4 text-right font-bold">
                          <span
                            className={
                              item.current_stock < item.reorder_point
                                ? "text-rose-600"
                                : "text-emerald-600"
                            }
                          >
                            {item.current_stock}
                          </span>
                        </td>
                        <td className="py-3 px-4 text-center">
                          {item.status === "REORDER_NEEDED" ? (
                            <Badge variant="warning">REORDER NEEDED</Badge>
                          ) : (
                            <Badge variant="success">SUFFICIENT</Badge>
                          )}
                        </td>
                        <td className="py-3 px-4 text-right font-bold">
                          {item.reorder_quantity > 0 ? (
                            <span className="text-amber-600">+{item.reorder_quantity}</span>
                          ) : (
                            <span className="text-slate-400">0</span>
                          )}
                        </td>
                        <td className="py-3 px-4 text-center">
                          <Button
                            variant={item.reorder_quantity > 0 ? "primary" : "outline"}
                            size="sm"
                            onClick={() => handleOpenDraftOrder(item)}
                            className="h-7 px-2.5 text-xs gap-1"
                          >
                            <ShoppingCart className="w-3 h-3" />
                            Draft Reorder
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Draft Reorder Modal */}
      {orderModalItem && (
        <Modal
          isOpen={!!orderModalItem}
          onClose={() => setOrderModalItem(null)}
          title={`Create Reorder Draft for ${orderModalItem.sku}`}
          description={`Replenish stock for ${orderModalItem.name} for ${currentDealer?.name}`}
          maxWidth="md"
          footer={
            <>
              <Button variant="outline" onClick={() => setOrderModalItem(null)}>
                Cancel
              </Button>
              {!createdOrder ? (
                <Button
                  variant="primary"
                  onClick={handleConfirmDraftOrder}
                  isLoading={isSubmittingOrder}
                  className="gap-1.5"
                >
                  <ShoppingCart className="w-3.5 h-3.5" />
                  Place Draft Reorder
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={() => {
                    setOrderModalItem(null);
                    onNavigate("orders");
                  }}
                >
                  View in Orders
                </Button>
              )}
            </>
          }
        >
          <div className="space-y-4 text-sm">
            {orderError && (
              <Alert variant="destructive" title="Reorder Draft Failed">
                {orderError}
              </Alert>
            )}

            {createdOrder ? (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl dark:bg-emerald-950/30 dark:border-emerald-900 text-center space-y-2">
                <CheckCircle className="w-8 h-8 text-emerald-600 mx-auto" />
                <h4 className="font-semibold text-emerald-900 dark:text-emerald-200">
                  Draft Reorder Placed!
                </h4>
                <p className="text-xs text-emerald-700 dark:text-emerald-300">
                  Order Number: <strong className="font-mono">{createdOrder.order_number}</strong>
                </p>
                <p className="text-xs text-slate-500">
                  Status is DRAFT. Navigate to Orders to confirm and reserve inventory.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800 text-xs space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current Stock:</span>
                    <span className="font-bold">{orderModalItem.current_stock} units</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Reorder Point (ROP):</span>
                    <span className="font-bold">{orderModalItem.reorder_point} units</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Recommended Order:</span>
                    <span className="font-bold text-amber-600">
                      +{orderModalItem.reorder_quantity} units
                    </span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                    Order Quantity to Reorder:
                  </label>
                  <Input
                    type="number"
                    min="1"
                    value={orderQty}
                    onChange={(e) => setOrderQty(Math.max(1, parseInt(e.target.value) || 1))}
                  />
                </div>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
