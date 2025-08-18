import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { isUnauthorizedError } from "@/lib/authUtils";
import Navigation from "@/components/navigation";
import BalanceCard from "@/components/balance-card";
import TradingConfig from "@/components/trading-config";
import BotControls from "@/components/bot-controls";
import RecentTrades from "@/components/recent-trades";

export default function Dashboard() {
  const { toast } = useToast();
  const { isAuthenticated, isLoading } = useAuth();

  // Redirect to home if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      toast({
        title: "Неавторизовано",
        description: "Ви не авторизовані. Перенаправлення на вхід...",
        variant: "destructive",
      });
      setTimeout(() => {
        window.location.href = "/api/login";
      }, 500);
      return;
    }
  }, [isAuthenticated, isLoading, toast]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-binance-bg flex items-center justify-center">
        <div className="text-binance-yellow text-xl">Завантаження...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-binance-bg text-binance-text font-inter">
      <Navigation />
      
      {/* Account Balance Card */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <BalanceCard />

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 mt-8">
          {/* Trading Configuration */}
          <div className="xl:col-span-2">
            <TradingConfig />
          </div>

          {/* Control Panel */}
          <div className="space-y-6">
            <BotControls />
            <RecentTrades />
          </div>
        </div>
      </div>
    </div>
  );
}
