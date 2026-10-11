import React, { useEffect, useState } from "react";
import {
  Search,
  Filter,
  Plus,
  Eye,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  PackageCheck,
  AlertCircle,
  Edit2,
} from "lucide-react";
import { Card, CardContent } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { Badge } from "../components/ui/Badge";
import { Modal } from "../components/ui/Modal";
import { Alert } from "../components/ui/Alert";
import { getProducts, createDraftOrder, updateInventory } from "../lib/api";
import type { Product, Order } from "../types/api";
import { formatCurrency } from "../lib/utils";
import { useDealer } from "../context/DealerContext";
import type { ActiveTab } from "../components/Layout";

interface CataloguePageProps {
  onNavigate: (tab: ActiveTab) => void;
}

export const CataloguePage: React.FC<CataloguePageProps> = ({ onNavigate }) => {
  const { currentDealer } = useDealer();

  // State
  const [products, setProducts] = useState<Product[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageSize = 12;

  const [search, setSearch] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [vehicle, setVehicle] = useState<string>("");

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [isDetailModalOpen, setIsDetailModalOpen] = useState<boolean>(false);

  // Quick inventory update inside detail modal
  const [adjustQuantity, setAdjustQuantity] = useState<number>(0);
  const [isAdjustingStock, setIsAdjustingStock] = useState<boolean>(false);
  const [stockUpdateSuccess, setStockUpdateSuccess] = useState<boolean>(false);

  // Add to Draft Order modal
  const [isOrderModalOpen, setIsOrderModalOpen] = useState<boolean>(false);
  const [orderQuantity, setOrderQuantity] = useState<number>(1);
  const [isCreatingOrder, setIsCreatingOrder] = useState<boolean>(false);
  const [createdOrder, setCreatedOrder] = useState<Order | null>(null);
  const [orderError, setOrderError] = useState<string | null>(null);

  const fetchProducts = async (page = 1) => {
    try {
      setIsLoading(true);
      setError(null);
      const res = await getProducts({
        search: search.trim() || undefined,
        category: category || undefined,
        vehicle: vehicle || undefined,
        page,
        page_size: pageSize,
      });
      setProducts(res.results);
      setTotalCount(res.count);
      setCurrentPage(page);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to load products from API.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProducts(1);
  }, [category, vehicle]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchProducts(1);
  };

  const totalPages = Math.ceil(totalCount / pageSize);

  const handleOpenDetail = (product: Product) => {
    setSelectedProduct(product);
    setAdjustQuantity(product.stock);
    setStockUpdateSuccess(false);
    setIsDetailModalOpen(true);
  };

  const handleOpenOrderModal = (product: Product) => {
    setSelectedProduct(product);
    setOrderQuantity(1);
    setCreatedOrder(null);
    setOrderError(null);
    setIsOrderModalOpen(true);
  };

  const handleUpdateStock = async () => {
    if (!selectedProduct) return;
    try {
      setIsAdjustingStock(true);
      await updateInventory(selectedProduct.sku, adjustQuantity, "Manual dashboard adjustment");
      setStockUpdateSuccess(true);
      setSelectedProduct({ ...selectedProduct, stock: adjustQuantity });
      // update list
      setProducts((prev) =>
        prev.map((p) => (p.sku === selectedProduct.sku ? { ...p, stock: adjustQuantity } : p))
      );
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(`Failed to update stock: ${err.message}`);
      }
    } finally {
      setIsAdjustingStock(false);
    }
  };

  const handleCreateOrder = async () => {
    if (!selectedProduct || !currentDealer) return;
    try {
      setIsCreatingOrder(true);
      setOrderError(null);
      const order = await createDraftOrder(currentDealer.id, [
        { sku: selectedProduct.sku, quantity: orderQuantity },
      ]);
      setCreatedOrder(order);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setOrderError(err.message);
      } else {
        setOrderError("Failed to create draft order.");
      }
    } finally {
      setIsCreatingOrder(false);
    }
  };

  const getStockBadge = (stock: number) => {
    if (stock > 10) {
      return <Badge variant="success">{stock} in stock</Badge>;
    }
    if (stock > 0) {
      return <Badge variant="warning">{stock} left (Low)</Badge>;
    }
    return <Badge variant="destructive">Out of Stock</Badge>;
  };

  return (
    <div className="space-y-6">
      {/* Header & Filter Controls */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">
            Automotive Parts Catalogue
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Showing {totalCount} verified automotive spare parts & components
          </p>
        </div>

        {/* Search & Filters */}
        <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-2">
          <div className="w-56 sm:w-64">
            <Input
              placeholder="Search by part name or SKU..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              icon={<Search className="w-4 h-4 text-slate-400" />}
            />
          </div>

          <div className="w-36">
            <Select
              aria-label="Filter by Category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              <option value="">All Categories</option>
              <option value="Engine">Engine</option>
              <option value="Brakes">Brakes</option>
              <option value="Transmission">Transmission</option>
              <option value="Electrical">Electrical</option>
              <option value="Suspension">Suspension</option>
              <option value="Filters">Filters</option>
              <option value="Exhaust">Exhaust</option>
              <option value="Cooling">Cooling</option>
            </Select>
          </div>

          <div className="w-36">
            <Select
              aria-label="Filter by Vehicle Fitment"
              value={vehicle}
              onChange={(e) => setVehicle(e.target.value)}
            >
              <option value="">All Vehicles</option>
              <option value="Maruti">Maruti Suzuki</option>
              <option value="Hyundai">Hyundai</option>
              <option value="Honda">Honda</option>
              <option value="Tata">Tata Motors</option>
              <option value="Mahindra">Mahindra</option>
              <option value="Toyota">Toyota</option>
            </Select>
          </div>

          <Button type="submit" variant="secondary" size="sm" className="gap-1.5">
            <Filter className="w-3.5 h-3.5" />
            Filter
          </Button>
        </form>
      </div>

      {error && (
        <Alert variant="destructive" title="Catalogue Error">
          {error}
        </Alert>
      )}

      {/* Product Cards Grid */}
      {isLoading ? (
        <div className="py-20 text-center">
          <div className="inline-block w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
          <p className="mt-3 text-sm text-slate-500">Loading parts catalogue...</p>
        </div>
      ) : products.length === 0 ? (
        <div className="py-16 text-center bg-white rounded-xl border border-slate-200 p-8 dark:bg-slate-900 dark:border-slate-800">
          <p className="text-base font-semibold text-slate-800 dark:text-slate-200">
            No matching automotive parts found
          </p>
          <p className="text-xs text-slate-500 mt-1">
            Try adjusting your search query, vehicle filter, or category filter.
          </p>
          <Button
            variant="outline"
            size="sm"
            className="mt-4"
            onClick={() => {
              setSearch("");
              setCategory("");
              setVehicle("");
              fetchProducts(1);
            }}
          >
            Clear Filters
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {products.map((product) => (
            <Card
              key={product.sku}
              className="flex flex-col justify-between hover:border-slate-300 dark:hover:border-slate-700 transition-all hover:shadow-xs"
            >
              <CardContent className="p-5 pb-3">
                <div className="flex items-start justify-between gap-2">
                  <span className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-950/50 px-2 py-0.5 rounded-md border border-blue-100 dark:border-blue-900">
                    {product.sku}
                  </span>
                  {getStockBadge(product.stock)}
                </div>

                <h3 className="font-semibold text-sm text-slate-900 dark:text-slate-100 mt-2.5 line-clamp-2 leading-snug">
                  {product.name}
                </h3>

                <div className="mt-2.5 space-y-1 text-xs text-slate-500">
                  <div className="flex items-center justify-between">
                    <span>Brand / Category:</span>
                    <span className="font-medium text-slate-700 dark:text-slate-300">
                      {product.brand} • {product.category}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Fitment:</span>
                    <span className="font-medium text-slate-700 dark:text-slate-300 truncate max-w-[180px]">
                      {product.vehicle_fitment || "Universal"}
                    </span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 flex items-baseline justify-between">
                  <span className="text-xs text-slate-400 font-medium">Dealer Price</span>
                  <div className="text-right">
                    <span className="text-base font-extrabold text-slate-900 dark:text-slate-100">
                      {formatCurrency(product.price)}
                    </span>
                    <span className="text-[10px] text-slate-400 block -mt-1">+ 18% GST</span>
                  </div>
                </div>
              </CardContent>

              {/* Action Buttons */}
              <div className="p-5 pt-0 flex gap-2 border-t border-slate-50 dark:border-slate-800/40">
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1 text-xs gap-1"
                  onClick={() => handleOpenDetail(product)}
                >
                  <Eye className="w-3.5 h-3.5" />
                  Details
                </Button>
                <Button
                  variant="primary"
                  size="sm"
                  className="flex-1 text-xs gap-1"
                  onClick={() => handleOpenOrderModal(product)}
                >
                  <Plus className="w-3.5 h-3.5" />
                  Draft Order
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-slate-200 pt-4 dark:border-slate-800">
          <p className="text-xs text-slate-500">
            Page <span className="font-medium text-slate-700 dark:text-slate-300">{currentPage}</span> of{" "}
            <span className="font-medium text-slate-700 dark:text-slate-300">{totalPages}</span> (
            {totalCount} total SKUs)
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage <= 1 || isLoading}
              onClick={() => fetchProducts(currentPage - 1)}
              className="gap-1 text-xs"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={currentPage >= totalPages || isLoading}
              onClick={() => fetchProducts(currentPage + 1)}
              className="gap-1 text-xs"
            >
              Next
              <ChevronRight className="w-3.5 h-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Product Detail Modal */}
      {selectedProduct && (
        <Modal
          isOpen={isDetailModalOpen}
          onClose={() => setIsDetailModalOpen(false)}
          title={selectedProduct.name}
          description={`SKU: ${selectedProduct.sku} • Brand: ${selectedProduct.brand}`}
          maxWidth="lg"
          footer={
            <Button variant="outline" onClick={() => setIsDetailModalOpen(false)}>
              Close
            </Button>
          }
        >
          <div className="space-y-4 text-sm">
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800 space-y-2">
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-slate-400 block">Category:</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {selectedProduct.category}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block">Unit Price (excl. GST):</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {formatCurrency(selectedProduct.price)}
                  </span>
                </div>
                <div className="col-span-2">
                  <span className="text-slate-400 block">Vehicle Compatibility:</span>
                  <span className="font-semibold text-slate-800 dark:text-slate-200">
                    {selectedProduct.vehicle_fitment || "All compatible models"}
                  </span>
                </div>
              </div>
            </div>

            <div>
              <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">
                Description
              </h4>
              <p className="text-slate-600 dark:text-slate-300 text-xs leading-relaxed">
                {selectedProduct.description || "No specific technical notes provided."}
              </p>
            </div>

            {/* Quick Inventory Adjuster */}
            <div className="border-t border-slate-200 pt-4 dark:border-slate-800">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                  <Edit2 className="w-3.5 h-3.5 text-blue-600" />
                  Quick Inventory Stock Adjustment
                </h4>
                {getStockBadge(selectedProduct.stock)}
              </div>
              <div className="flex items-center gap-2">
                <Input
                  type="number"
                  min="0"
                  value={adjustQuantity}
                  onChange={(e) => setAdjustQuantity(Math.max(0, parseInt(e.target.value) || 0))}
                  className="w-32"
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleUpdateStock}
                  isLoading={isAdjustingStock}
                  className="text-xs"
                >
                  Save Stock
                </Button>
                {stockUpdateSuccess && (
                  <span className="text-xs text-emerald-600 flex items-center gap-1">
                    <CheckCircle2 className="w-3.5 h-3.5" /> Updated
                  </span>
                )}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* Add to Draft Order Modal */}
      {selectedProduct && (
        <Modal
          isOpen={isOrderModalOpen}
          onClose={() => setIsOrderModalOpen(false)}
          title="Create Draft Order"
          description={`Add ${selectedProduct.name} to a new purchase order for ${currentDealer?.name || "dealer"}`}
          maxWidth="md"
          footer={
            <>
              <Button variant="outline" onClick={() => setIsOrderModalOpen(false)}>
                Cancel
              </Button>
              {!createdOrder ? (
                <Button
                  variant="primary"
                  onClick={handleCreateOrder}
                  isLoading={isCreatingOrder}
                  className="gap-1.5"
                >
                  <PackageCheck className="w-4 h-4" />
                  Create Draft Order
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={() => {
                    setIsOrderModalOpen(false);
                    onNavigate("orders");
                  }}
                  className="gap-1.5"
                >
                  View in Orders
                </Button>
              )}
            </>
          }
        >
          <div className="space-y-4 text-sm">
            {orderError && (
              <Alert variant="destructive" title="Order Creation Error">
                {orderError}
              </Alert>
            )}

            {createdOrder ? (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl dark:bg-emerald-950/30 dark:border-emerald-900 text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto" />
                <h4 className="font-semibold text-emerald-900 dark:text-emerald-200">
                  Draft Order Created Successfully!
                </h4>
                <p className="text-xs text-emerald-700 dark:text-emerald-300">
                  Order Number: <strong className="font-mono">{createdOrder.order_number}</strong>
                </p>
                <p className="text-xs text-slate-500">
                  Status is DRAFT. Stock is reserved only when confirmed on the Orders page.
                </p>
              </div>
            ) : (
              <div className="space-y-4">
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800 text-xs space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Target Dealer:</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      {currentDealer?.name} ({currentDealer?.dealer_code})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Item SKU:</span>
                    <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                      {selectedProduct.sku}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Unit Price:</span>
                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                      {formatCurrency(selectedProduct.price)}
                    </span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                    Order Quantity:
                  </label>
                  <Input
                    type="number"
                    min="1"
                    max="1000"
                    value={orderQuantity}
                    onChange={(e) => setOrderQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                  />
                </div>

                {/* Live total estimation */}
                <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-lg text-xs space-y-1 dark:bg-blue-950/20 dark:border-blue-900">
                  <div className="flex justify-between text-slate-600 dark:text-slate-400">
                    <span>Subtotal:</span>
                    <span>{formatCurrency(parseFloat(selectedProduct.price) * orderQuantity)}</span>
                  </div>
                  <div className="flex justify-between text-slate-600 dark:text-slate-400">
                    <span>GST (18%):</span>
                    <span>
                      {formatCurrency(parseFloat(selectedProduct.price) * orderQuantity * 0.18)}
                    </span>
                  </div>
                  <div className="flex justify-between font-bold text-slate-900 dark:text-slate-100 pt-1 border-t border-blue-200/50">
                    <span>Estimated Total:</span>
                    <span>
                      {formatCurrency(parseFloat(selectedProduct.price) * orderQuantity * 1.18)}
                    </span>
                  </div>
                </div>

                {selectedProduct.stock < orderQuantity && (
                  <p className="text-xs text-amber-600 flex items-center gap-1">
                    <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                    Available stock ({selectedProduct.stock}) is lower than requested quantity. Order
                    can be created as DRAFT, but will require stock before confirmation.
                  </p>
                )}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
