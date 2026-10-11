import React, { createContext, useContext, useState, useEffect } from "react";
import type { Dealer } from "../types/api";
import { getDealers } from "../lib/api";

interface DealerContextValue {
  dealers: Dealer[];
  currentDealer: Dealer | null;
  setCurrentDealer: (dealer: Dealer) => void;
  isLoading: boolean;
  refreshDealers: () => Promise<void>;
}

const DealerContext = createContext<DealerContextValue | undefined>(undefined);

export const DealerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [dealers, setDealers] = useState<Dealer[]>([]);
  const [currentDealer, setCurrentDealer] = useState<Dealer | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const fetchDealers = async () => {
    try {
      setIsLoading(true);
      const res = await getDealers(1, 50);
      setDealers(res.results);
      if (res.results.length > 0) {
        // preserve or set first
        setCurrentDealer((prev) => {
          if (!prev) return res.results[0];
          const found = res.results.find((d) => d.id === prev.id);
          return found || res.results[0];
        });
      }
    } catch (err) {
      console.error("Failed to load dealers:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchDealers();
  }, []);

  return (
    <DealerContext.Provider
      value={{
        dealers,
        currentDealer,
        setCurrentDealer,
        isLoading,
        refreshDealers: fetchDealers,
      }}
    >
      {children}
    </DealerContext.Provider>
  );
};

export function useDealer(): DealerContextValue {
  const context = useContext(DealerContext);
  if (!context) {
    throw new Error("useDealer must be used within a DealerProvider");
  }
  return context;
}
