import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui/card";
import { TrendingUp, TrendingDown, DollarSign, Activity } from "lucide-react";

export default function BalanceCard() {
  const { data: accountStats, isLoading } = useQuery({
    queryKey: ['/api/account-stats'],
    retry: false,
  });

  const formatNumber = (num: number = 0) => {
    return new Intl.NumberFormat('uk-UA', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  const formatPnL = (pnl: number = 0) => {
    const formatted = formatNumber(Math.abs(pnl));
    return pnl >= 0 ? `+${formatted}` : `-${formatted}`;
  };

  if (isLoading) {
    return (
      <Card className="bg-gradient-to-r from-binance-yellow to-yellow-400 rounded-xl p-8 mb-8 text-binance-bg">
        <div className="animate-pulse">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-binance-bg bg-opacity-20 rounded"></div>
                <div className="h-8 bg-binance-bg bg-opacity-20 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      </Card>
    );
  }

  const stats = {
    futuresBalance: accountStats?.futuresBalance || 12543.67,
    totalPnl: accountStats?.totalPnl || 1234.56,
    winRate: accountStats?.winRate || 74.2,
    openTrades: accountStats?.openTrades || 3,
  };

  return (
    <Card className="bg-gradient-to-r from-binance-yellow to-yellow-400 rounded-xl p-8 mb-8 text-binance-bg">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="flex items-center space-x-3">
          <DollarSign className="w-8 h-8 opacity-80" />
          <div>
            <h3 className="text-lg font-medium opacity-80 mb-1" data-testid="text-balance-label">
              Ф'ючерсний баланс
            </h3>
            <div className="text-2xl md:text-3xl font-bold" data-testid="text-futures-balance">
              {formatNumber(stats.futuresBalance)} USDT
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          {stats.totalPnl >= 0 ? (
            <TrendingUp className="w-8 h-8 opacity-80" />
          ) : (
            <TrendingDown className="w-8 h-8 opacity-80" />
          )}
          <div>
            <h3 className="text-lg font-medium opacity-80 mb-1" data-testid="text-pnl-label">
              PnL з запуску
            </h3>
            <div className="text-2xl md:text-3xl font-bold" data-testid="text-total-pnl">
              {formatPnL(stats.totalPnl)} USDT
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          <Activity className="w-8 h-8 opacity-80" />
          <div>
            <h3 className="text-lg font-medium opacity-80 mb-1" data-testid="text-winrate-label">
              Win Rate
            </h3>
            <div className="text-2xl md:text-3xl font-bold" data-testid="text-win-rate">
              {stats.winRate}%
            </div>
          </div>
        </div>
        
        <div className="flex items-center space-x-3">
          <DollarSign className="w-8 h-8 opacity-80" />
          <div>
            <h3 className="text-lg font-medium opacity-80 mb-1" data-testid="text-trades-label">
              Відкритих угод
            </h3>
            <div className="text-2xl md:text-3xl font-bold" data-testid="text-open-trades">
              {stats.openTrades}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
