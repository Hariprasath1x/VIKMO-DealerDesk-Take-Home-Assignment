import { useState, useEffect } from "react";
import { DealerProvider } from "./context/DealerContext";
import { Layout, type ActiveTab } from "./components/Layout";
import { DashboardPage } from "./pages/DashboardPage";
import { CataloguePage } from "./pages/CataloguePage";
import { OrdersPage } from "./pages/OrdersPage";
import { AssistantPage } from "./pages/AssistantPage";
import { ForecastPage } from "./pages/ForecastPage";
import { SupplierSyncModal } from "./components/SupplierSyncModal";

export function App() {
  // Sync tab with URL hash for easy bookmarking and refresh persistence
  const [activeTab, setActiveTabState] = useState<ActiveTab>(() => {
    const hash = window.location.hash.replace("#", "") as ActiveTab;
    if (["dashboard", "catalogue", "orders", "assistant", "forecast"].includes(hash)) {
      return hash;
    }
    return "dashboard";
  });

  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);

  const setActiveTab = (tab: ActiveTab) => {
    setActiveTabState(tab);
    window.location.hash = `#${tab}`;
  };

  useEffect(() => {
    const handleHashChange = () => {
      const hash = window.location.hash.replace("#", "") as ActiveTab;
      if (["dashboard", "catalogue", "orders", "assistant", "forecast"].includes(hash)) {
        setActiveTabState(hash);
      }
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  return (
    <DealerProvider>
      <Layout activeTab={activeTab} setActiveTab={setActiveTab}>
        {activeTab === "dashboard" && (
          <DashboardPage
            onNavigate={setActiveTab}
            onOpenSync={() => setIsSyncModalOpen(true)}
          />
        )}
        {activeTab === "catalogue" && <CataloguePage onNavigate={setActiveTab} />}
        {activeTab === "orders" && <OrdersPage />}
        {activeTab === "assistant" && <AssistantPage onNavigate={setActiveTab} />}
        {activeTab === "forecast" && <ForecastPage onNavigate={setActiveTab} />}
      </Layout>

      <SupplierSyncModal
        isOpen={isSyncModalOpen}
        onClose={() => setIsSyncModalOpen(false)}
      />
    </DealerProvider>
  );
}

export default App;
