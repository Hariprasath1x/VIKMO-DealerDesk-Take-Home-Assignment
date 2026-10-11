import React, { useState } from "react";
import { Modal } from "./ui/Modal";
import { Button } from "./ui/Button";
import { Alert } from "./ui/Alert";
import { triggerSupplierSync } from "../lib/api";
import type { SupplierSyncResponse } from "../types/api";
import { RefreshCw, CheckCircle2, AlertTriangle, Database } from "lucide-react";

interface SupplierSyncModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSyncComplete?: () => void;
}

export const SupplierSyncModal: React.FC<SupplierSyncModalProps> = ({
  isOpen,
  onClose,
  onSyncComplete,
}) => {
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<SupplierSyncResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleStartSync = async () => {
    try {
      setLoading(true);
      setError(null);
      setResult(null);
      const res = await triggerSupplierSync();
      setResult(res);
      if (onSyncComplete) onSyncComplete();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Failed to synchronize with supplier feed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    if (!loading) {
      setResult(null);
      setError(null);
      onClose();
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Supplier Catalogue Synchronization"
      description="Fetch and synchronize products from the upstream supplier catalogue API."
      maxWidth="lg"
      footer={
        <>
          <Button variant="outline" onClick={handleClose} disabled={loading}>
            {result ? "Done" : "Cancel"}
          </Button>
          {!result && (
            <Button
              variant="primary"
              onClick={handleStartSync}
              isLoading={loading}
              className="gap-2"
            >
              <RefreshCw className="w-4 h-4" />
              Start Synchronization
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {error && (
          <Alert variant="destructive" title="Sync Failed">
            {error}
          </Alert>
        )}

        {loading && (
          <div className="py-8 flex flex-col items-center justify-center space-y-4 text-center">
            <RefreshCw className="w-10 h-10 text-blue-600 animate-spin" />
            <div>
              <p className="font-semibold text-slate-800">Synchronizing Supplier Feed...</p>
              <p className="text-sm text-slate-500 mt-1">
                Fetching pages, verifying SKU integrity, and applying catalogue updates.
              </p>
            </div>
          </div>
        )}

        {!loading && !result && (
          <div className="space-y-3 text-sm text-slate-600 dark:text-slate-300">
            <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 dark:bg-slate-800/40 dark:border-slate-800 flex gap-3">
              <Database className="w-5 h-5 text-blue-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-slate-900 dark:text-slate-100">
                  Two-Stage Atomic Synchronization
                </p>
                <p className="mt-1 text-slate-500 dark:text-slate-400">
                  Sync retrieves all pages with automatic rate-limit backoff (HTTP 429), deduplicates
                  items, and atomically updates the catalogue. Existing dealer inventory counts are
                  strictly preserved.
                </p>
              </div>
            </div>
            <p>Click "Start Synchronization" to pull recent supplier catalogue updates now.</p>
          </div>
        )}

        {result && (
          <div className="space-y-4">
            <div className="flex items-center gap-2 text-emerald-600 font-semibold">
              <CheckCircle2 className="w-5 h-5" />
              <span>Synchronization Completed Successfully</span>
            </div>

            <div className="grid grid-cols-3 gap-3">
              <div className="bg-emerald-50 border border-emerald-100 p-3 rounded-lg text-center dark:bg-emerald-950/30 dark:border-emerald-900">
                <span className="block text-2xl font-bold text-emerald-700 dark:text-emerald-300">
                  {result.created}
                </span>
                <span className="text-xs text-emerald-600 dark:text-emerald-400 font-medium">
                  Created
                </span>
              </div>
              <div className="bg-blue-50 border border-blue-100 p-3 rounded-lg text-center dark:bg-blue-950/30 dark:border-blue-900">
                <span className="block text-2xl font-bold text-blue-700 dark:text-blue-300">
                  {result.updated}
                </span>
                <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">
                  Updated
                </span>
              </div>
              <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg text-center dark:bg-slate-800/50 dark:border-slate-700">
                <span className="block text-2xl font-bold text-slate-700 dark:text-slate-300">
                  {result.unchanged}
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400 font-medium">
                  Unchanged
                </span>
              </div>
            </div>

            <div className="text-xs text-slate-500 space-y-1">
              <p>Pages fetched: <strong className="text-slate-700 dark:text-slate-300">{result.pages_fetched}</strong></p>
              <p>HTTP requests made: <strong className="text-slate-700 dark:text-slate-300">{result.requests_made}</strong></p>
            </div>

            {result.rejected && result.rejected.length > 0 && (
              <div className="mt-3 p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs space-y-1 dark:bg-amber-950/30 dark:border-amber-900">
                <div className="flex items-center gap-1.5 font-semibold text-amber-800 dark:text-amber-300">
                  <AlertTriangle className="w-4 h-4" />
                  <span>Rejected Items ({result.rejected.length})</span>
                </div>
                <div className="max-h-24 overflow-y-auto space-y-1 mt-1">
                  {result.rejected.map((rej, i) => (
                    <div key={i} className="text-amber-700 dark:text-amber-400">
                      <code>{rej.supplier_sku}</code>: {rej.reason}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
};
