import React, { useEffect, useState } from "react";
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  Eye,
  RefreshCw,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Alert } from "../components/ui/Alert";
import {
  getOrders,
  getOrder,
  confirmOrder,
  cancelOrder,
  dispatchOrder,
  deliverOrder,
  APIClientError,
} from "../lib/api";
import type { Order, OrderStatus } from "../types/api";
import { formatCurrency, formatDate } from "../lib/utils";
import { useDealer } from "../context/DealerContext";

export const OrdersPage: React.FC = () => {
  const { currentDealer } = useDealer();

  const [orders, setOrders] = useState<Order[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const pageSize = 10;

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Selected Order for Detail View
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);

  // Lifecycle Action State
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [actionError, setActionError] = useState<{
    code: string;
    message: string;
    details?: Array<{ sku: string; requested: number; available: number }>;
  } | null>(null);

  // Confirmation Prompt State
  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    action: "confirm" | "cancel" | "dispatch" | "deliver";
    orderNumber: string;
    title: string;
    message: string;
  }>({
    isOpen: false,
    action: "confirm",
    orderNumber: "",
    title: "",
    message: "",
  });

  const fetchOrders = async (page = 1) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await getOrders({
        dealer_id: currentDealer?.id,
        status: statusFilter || undefined,
        page,
        page_size: pageSize,
      });
      setOrders(res.results);
      setTotalCount(res.count);
      setCurrentPage(page);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to fetch orders.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchOrders(1);
  }, [currentDealer, statusFilter]);

  const handleOpenDetail = async (orderNumber: string) => {
    try {
      setIsDetailModalOpen(true);
      setActionError(null);
      const fullOrder = await getOrder(orderNumber);
      setSelectedOrder(fullOrder);
    } catch (err: unknown) {
      console.error(err);
    }
  };

  const handlePromptAction = (
    action: "confirm" | "cancel" | "dispatch" | "deliver",
    order: Order
  ) => {
    const titles = {
      confirm: "Confirm Order & Reserve Stock",
      cancel: "Cancel Order",
      dispatch: "Mark Order as Dispatched",
      deliver: "Mark Order as Delivered",
    };
    const messages = {
      confirm: `Are you sure you want to confirm order ${order.order_number}? This will validate catalogue stock and atomically decrement inventory.`,
      cancel: `Are you sure you want to cancel order ${order.order_number}? If previously confirmed, stock will be safely returned to inventory.`,
      dispatch: `Confirm dispatch for shipment ${order.order_number}?`,
      deliver: `Confirm successful delivery for order ${order.order_number}?`,
    };

    setConfirmDialog({
      isOpen: true,
      action,
      orderNumber: order.order_number,
      title: titles[action],
      message: messages[action],
    });
  };

  const executeConfirmedAction = async () => {
    const { action, orderNumber } = confirmDialog;
    setConfirmDialog((prev) => ({ ...prev, isOpen: false }));
    setActionLoading(true);
    setActionError(null);

    try {
      let updatedOrder: Order;
      if (action === "confirm") {
        updatedOrder = await confirmOrder(orderNumber);
      } else if (action === "cancel") {
        updatedOrder = await cancelOrder(orderNumber);
      } else if (action === "dispatch") {
        updatedOrder = await dispatchOrder(orderNumber);
      } else {
        updatedOrder = await deliverOrder(orderNumber);
      }

      // Update both current detail and list
      setSelectedOrder(updatedOrder);
      setOrders((prev) =>
        prev.map((o) => (o.order_number === updatedOrder.order_number ? updatedOrder : o))
      );
    } catch (err: unknown) {
      if (err instanceof APIClientError) {
        setActionError({
          code: err.code,
          message: err.message,
          details: err.details as Array<{ sku: string; requested: number; available: number }>,
        });
      } else if (err instanceof Error) {
        setActionError({
          code: "ACTION_FAILED",
          message: err.message,
        });
      }
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status: OrderStatus) => {
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

  const totalPages = Math.ceil(totalCount / pageSize);

  const statusTabs: Array<{ id: string; label: string }> = [
    { id: "", label: "All Orders" },
    { id: "DRAFT", label: "Draft" },
    { id: "CONFIRMED", label: "Confirmed" },
    { id: "DISPATCHED", label: "Dispatched" },
    { id: "DELIVERED", label: "Delivered" },
    { id: "CANCELLED", label: "Cancelled" },
  ];

  return (
    <div className="space-y-6">
      {/* Header & Status Filter Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
            Dealer Orders & Fulfillment
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Manage purchase orders, atomic inventory reservations, and 18% GST tax breakdowns
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchOrders(currentPage)}
          className="gap-1.5 self-start text-xs"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 border-b border-slate-200 dark:border-slate-800 overflow-x-auto pb-1">
        {statusTabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
            className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors whitespace-nowrap cursor-pointer ${
              statusFilter === tab.id
                ? "bg-blue-600 text-white shadow-xs"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error && (
        <Alert variant="destructive" title="Error loading orders">
          {error}
        </Alert>
      )}

      {/* Orders Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="py-20 text-center">
              <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
              <p className="mt-3 text-sm text-slate-500">Loading purchase orders...</p>
            </div>
          ) : orders.length === 0 ? (
            <div className="py-16 text-center">
              <FileText className="w-10 h-10 text-slate-300 mx-auto mb-2" />
              <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                No orders found
              </p>
              <p className="text-xs text-slate-400 mt-0.5">
                {statusFilter
                  ? `No orders matching status '${statusFilter}' for current dealer.`
                  : "You can create draft orders from the Parts Catalogue or ask the AI Assistant."}
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 dark:border-slate-800 dark:bg-slate-800/50">
                    <th className="py-3 px-4 font-semibold">Order Number</th>
                    <th className="py-3 px-4 font-semibold">Created At</th>
                    <th className="py-3 px-4 font-semibold">Status</th>
                    <th className="py-3 px-4 font-semibold text-center">Items</th>
                    <th className="py-3 px-4 font-semibold text-right">Subtotal</th>
                    <th className="py-3 px-4 font-semibold text-right">GST (18%)</th>
                    <th className="py-3 px-4 font-semibold text-right">Grand Total</th>
                    <th className="py-3 px-4 font-semibold text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {orders.map((order) => (
                    <tr
                      key={order.order_number}
                      className="hover:bg-slate-50/50 transition-colors dark:hover:bg-slate-800/30"
                    >
                      <td className="py-3 px-4 font-mono font-bold text-blue-600 dark:text-blue-400">
                        {order.order_number}
                      </td>
                      <td className="py-3 px-4 text-slate-600 dark:text-slate-400">
                        {formatDate(order.created_at)}
                      </td>
                      <td className="py-3 px-4">{getStatusBadge(order.status)}</td>
                      <td className="py-3 px-4 text-center font-medium text-slate-700 dark:text-slate-300">
                        {order.items.length}
                      </td>
                      <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-400 font-medium">
                        {formatCurrency(order.subtotal)}
                      </td>
                      <td className="py-3 px-4 text-right text-slate-600 dark:text-slate-400 font-medium">
                        {formatCurrency(order.tax_total)}
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900 dark:text-slate-100">
                        {formatCurrency(order.grand_total)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleOpenDetail(order.order_number)}
                          className="text-xs h-7 px-2.5 gap-1"
                        >
                          <Eye className="w-3 h-3" />
                          View
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-200 pt-4 dark:border-slate-800">
          <p className="text-xs text-slate-500">
            Page {currentPage} of {totalPages} ({totalCount} total orders)
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1 || isLoading}
              onClick={() => fetchOrders(currentPage - 1)}
              className="gap-1 text-xs"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages || isLoading}
              onClick={() => fetchOrders(currentPage + 1)}
              className="gap-1 text-xs"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Order Detail Modal */}
      {selectedOrder && (
        <Modal
          isOpen={isDetailModalOpen}
          onClose={() => setIsDetailModalOpen(false)}
          title={`Order ${selectedOrder.order_number}`}
          description={`Placed on ${formatDate(selectedOrder.created_at)}`}
          maxWidth="2xl"
          footer={
            <div className="flex flex-wrap items-center justify-between w-full gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsDetailModalOpen(false)}
              >
                Close
              </Button>

              {/* Permitted state transition buttons based on backend contract */}
              <div className="flex items-center gap-2">
                {selectedOrder.status === "DRAFT" && (
                  <>
                    <Button
                      variant="destructive"
                      size="sm"
                      isLoading={actionLoading}
                      onClick={() => handlePromptAction("cancel", selectedOrder)}
                    >
                      Cancel Draft
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      isLoading={actionLoading}
                      onClick={() => handlePromptAction("confirm", selectedOrder)}
                    >
                      Confirm Order
                    </Button>
                  </>
                )}

                {selectedOrder.status === "CONFIRMED" && (
                  <>
                    <Button
                      variant="destructive"
                      size="sm"
                      isLoading={actionLoading}
                      onClick={() => handlePromptAction("cancel", selectedOrder)}
                    >
                      Cancel Order
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      isLoading={actionLoading}
                      onClick={() => handlePromptAction("dispatch", selectedOrder)}
                    >
                      Mark Dispatched
                    </Button>
                  </>
                )}

                {selectedOrder.status === "DISPATCHED" && (
                  <Button
                    variant="success"
                    size="sm"
                    isLoading={actionLoading}
                    onClick={() => handlePromptAction("deliver", selectedOrder)}
                  >
                    Mark Delivered
                  </Button>
                )}
              </div>
            </div>
          }
        >
          <div className="space-y-4">
            {/* Action Error Notification */}
            {actionError && (
              <Alert variant="destructive" title={`Action Failed: ${actionError.code}`}>
                <p>{actionError.message}</p>
                {actionError.details && actionError.details.length > 0 && (
                  <div className="mt-2 text-xs bg-rose-100/60 p-2 rounded dark:bg-rose-950/40">
                    <p className="font-semibold mb-1">Insufficient stock details:</p>
                    {actionError.details.map((d, i) => (
                      <div key={i}>
                        SKU <span className="font-mono">{d.sku}</span>: Requested {d.requested},{" "}
                        only {d.available} available in inventory.
                      </div>
                    ))}
                  </div>
                )}
              </Alert>
            )}

            {/* Status and Overview Bar */}
            <div className="flex items-center justify-between p-3.5 bg-slate-50 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800">
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500 font-medium">Status:</span>
                {getStatusBadge(selectedOrder.status)}
              </div>
              <div className="text-xs text-slate-500">
                Dealer ID:{" "}
                <span className="font-semibold text-slate-700 dark:text-slate-300">
                  {selectedOrder.dealer_id}
                </span>
              </div>
            </div>

            {/* Items Table */}
            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Order Line Items
              </h4>
              <div className="border border-slate-200 rounded-lg overflow-hidden dark:border-slate-800">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-slate-50 border-b border-slate-200 text-slate-500 dark:bg-slate-800 dark:border-slate-700">
                      <th className="p-2.5 font-semibold">Part</th>
                      <th className="p-2.5 font-semibold text-center">Qty</th>
                      <th className="p-2.5 font-semibold text-right">Unit Price</th>
                      <th className="p-2.5 font-semibold text-right">Subtotal</th>
                      <th className="p-2.5 font-semibold text-right">GST (18%)</th>
                      <th className="p-2.5 font-semibold text-right">Line Total</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {selectedOrder.items.map((item, idx) => (
                      <tr key={idx}>
                        <td className="p-2.5">
                          <span className="font-mono font-semibold text-blue-600 block">
                            {item.sku}
                          </span>
                          <span className="text-slate-700 dark:text-slate-300 text-[11px]">
                            {item.name}
                          </span>
                        </td>
                        <td className="p-2.5 text-center font-bold">{item.quantity}</td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                          {formatCurrency(item.unit_price)}
                        </td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                          {formatCurrency(item.line_subtotal)}
                        </td>
                        <td className="p-2.5 text-right font-mono text-slate-600 dark:text-slate-400">
                          {formatCurrency(item.line_tax)}
                        </td>
                        <td className="p-2.5 text-right font-mono font-bold text-slate-900 dark:text-slate-100">
                          {formatCurrency(item.line_total)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* GST Financial Summary */}
            <div className="bg-slate-50 p-4 rounded-xl border border-slate-200 space-y-2 dark:bg-slate-800/40 dark:border-slate-800 text-xs">
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Subtotal (Items Excl. Tax):</span>
                <span className="font-mono font-medium">
                  {formatCurrency(selectedOrder.subtotal)}
                </span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>Total GST (CGST 9% + SGST 9%):</span>
                <span className="font-mono font-medium">
                  {formatCurrency(selectedOrder.tax_total)}
                </span>
              </div>
              <div className="flex justify-between text-sm font-extrabold text-slate-900 dark:text-slate-100 pt-2 border-t border-slate-200 dark:border-slate-700">
                <span>Grand Total (Payable):</span>
                <span className="font-mono text-blue-600 dark:text-blue-400">
                  {formatCurrency(selectedOrder.grand_total)}
                </span>
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Confirmation Prompt Dialog */}
      <Modal
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
        title={confirmDialog.title}
        maxWidth="md"
        footer={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setConfirmDialog((prev) => ({ ...prev, isOpen: false }))}
            >
              Cancel
            </Button>
            <Button
              variant={confirmDialog.action === "cancel" ? "destructive" : "primary"}
              size="sm"
              onClick={executeConfirmedAction}
            >
              Confirm
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">
          {confirmDialog.message}
        </p>
      </Modal>
    </div>
  );
};
