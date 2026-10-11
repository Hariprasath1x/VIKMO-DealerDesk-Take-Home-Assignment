import React, { useState } from "react";
import {
  LayoutDashboard,
  Package,
  FileText,
  BotMessageSquare,
  TrendingUp,
  RefreshCw,
  Store,
  Menu,
  X,
} from "lucide-react";
import { useDealer } from "../context/DealerContext";
import { Button } from "./ui/Button";
import { SupplierSyncModal } from "./SupplierSyncModal";
import { cn } from "../lib/utils";

export type ActiveTab = "dashboard" | "catalogue" | "orders" | "assistant" | "forecast";

interface LayoutProps {
  activeTab: ActiveTab;
  setActiveTab: (tab: ActiveTab) => void;
  children: React.ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ activeTab, setActiveTab, children }) => {
  const { currentDealer, dealers, setCurrentDealer, isLoading } = useDealer();
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  const navItems: Array<{ id: ActiveTab; label: string; icon: React.ReactNode }> = [
    { id: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="w-5 h-5" /> },
    { id: "catalogue", label: "Parts Catalogue", icon: <Package className="w-5 h-5" /> },
    { id: "orders", label: "Orders", icon: <FileText className="w-5 h-5" /> },
    { id: "assistant", label: "AI Dealer Assistant", icon: <BotMessageSquare className="w-5 h-5" /> },
    { id: "forecast", label: "Forecast & Reorder", icon: <TrendingUp className="w-5 h-5" /> },
  ];

  return (
    <div className="min-h-screen flex bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 font-sans">
      {/* Mobile Sidebar Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-xs lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-white flex flex-col transition-transform duration-200 ease-in-out lg:translate-x-0 border-r border-slate-800",
          isMobileMenuOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        {/* Brand Header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-slate-800 bg-slate-950/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center font-black tracking-wider text-white shadow-sm">
              DD
            </div>
            <div>
              <span className="font-bold text-base tracking-tight text-white">DealerDesk</span>
              <span className="block text-[10px] text-blue-400 font-medium uppercase tracking-wider">
                VIKMO Automotive
              </span>
            </div>
          </div>
          <button
            type="button"
            className="lg:hidden text-slate-400 hover:text-white"
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  setIsMobileMenuOpen(false);
                }}
                className={cn(
                  "w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all cursor-pointer",
                  isActive
                    ? "bg-blue-600 text-white shadow-sm font-semibold"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                )}
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40 space-y-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsSyncModalOpen(true)}
            className="w-full justify-center bg-slate-800/80 border-slate-700 text-slate-200 hover:bg-slate-700 hover:text-white text-xs gap-2"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Sync Supplier Feed
          </Button>

          <div className="flex items-center gap-2 px-1 text-[11px] text-slate-400">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>Django API Online</span>
          </div>
        </div>
      </aside>

      {/* Main Content Wrap */}
      <div className="flex-1 flex flex-col lg:pl-64 min-w-0">
        {/* Top Navbar */}
        <header className="sticky top-0 z-30 h-16 bg-white/95 backdrop-blur-xs border-b border-slate-200 px-4 sm:px-6 flex items-center justify-between dark:bg-slate-900/95 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              onClick={() => setIsMobileMenuOpen(true)}
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-base font-semibold text-slate-900 dark:text-slate-100 capitalize">
                {activeTab === "assistant"
                  ? "AI Dealer Assistant"
                  : activeTab === "catalogue"
                  ? "Parts Catalogue"
                  : activeTab === "orders"
                  ? "Order Management"
                  : activeTab === "forecast"
                  ? "Forecast & Reorder Intelligence"
                  : "Dealer Dashboard"}
              </h1>
              <p className="text-xs text-slate-500 dark:text-slate-400 hidden sm:block">
                VIKMO Automotive B2B Distribution Portal
              </p>
            </div>
          </div>

          {/* Right Header: Active Dealer Selector */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-100 py-1.5 px-3 rounded-lg border border-slate-200 dark:bg-slate-800 dark:border-slate-700">
              <Store className="w-4 h-4 text-slate-500 dark:text-slate-400 shrink-0" />
              <div className="flex flex-col">
                <span className="text-[10px] uppercase font-semibold text-slate-400 dark:text-slate-500 leading-none">
                  Active Dealer
                </span>
                <select
                  aria-label="Active Dealer"
                  className="bg-transparent text-xs font-semibold text-slate-800 dark:text-slate-100 focus:outline-none cursor-pointer pr-1"
                  value={currentDealer?.id || ""}
                  disabled={isLoading}
                  onChange={(e) => {
                    const found = dealers.find((d) => d.id === Number(e.target.value));
                    if (found) setCurrentDealer(found);
                  }}
                >
                  {dealers.map((d) => (
                    <option key={d.id} value={d.id} className="text-slate-900 bg-white dark:bg-slate-900 dark:text-slate-100">
                      {d.dealer_code} - {d.name} ({d.city})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsSyncModalOpen(true)}
              className="hidden sm:inline-flex gap-1.5 text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5 text-slate-500" />
              Sync Feed
            </Button>
          </div>
        </header>

        {/* Main Page Container */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>

      {/* Global Supplier Sync Modal */}
      <SupplierSyncModal
        isOpen={isSyncModalOpen}
        onClose={() => setIsSyncModalOpen(false)}
      />
    </div>
  );
};
