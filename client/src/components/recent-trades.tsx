import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { formatDistanceToNow } from "date-fns";
import { uk } from "date-fns/locale";

export default function RecentTrades() {
  const { data: tradingHistory = [], isLoading } = useQuery({
    queryKey: ['/api/trading-history'],
    retry: false,
  });

  const formatPnL = (pnl: number) => {
    const formatted = new Intl.NumberFormat('uk-UA', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
    }).format(Math.abs(pnl));
    return pnl >= 0 ? `+${formatted}` : `-${formatted}`;
  };

  const formatTime = (date: string) => {
    return formatDistanceToNow(new Date(date), { 
      addSuffix: true, 
      locale: uk 
    });
  };

  if (isLoading) {
    return (
      <Card className="bg-binance-card border-binance-border">
        <CardHeader className="border-b border-binance-border">
          <CardTitle className="text-lg font-semibold">Останні угоди</CardTitle>
        </CardHeader>
        <CardContent className="p-6">
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse p-3 bg-binance-bg rounded-lg">
                <div className="flex items-center justify-between">
                  <div className="space-y-2">
                    <div className="h-4 bg-binance-border rounded w-16"></div>
                    <div className="h-3 bg-binance-border rounded w-12"></div>
                  </div>
                  <div className="space-y-2 text-right">
                    <div className="h-4 bg-binance-border rounded w-16"></div>
                    <div className="h-3 bg-binance-border rounded w-20"></div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  // Mock data if no trades exist
  const trades = tradingHistory.length > 0 ? tradingHistory : [
    {
      id: 'mock-1',
      symbol: 'BTCUSDT',
      side: 'long',
      pnl: 48.20,
      pnlPercentage: 2.4,
      createdAt: new Date(Date.now() - 2 * 60 * 1000).toISOString(), // 2 minutes ago
    },
    {
      id: 'mock-2',
      symbol: 'ETHUSDT',
      side: 'short',
      pnl: -12.00,
      pnlPercentage: -1.2,
      createdAt: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 minutes ago
    },
    {
      id: 'mock-3',
      symbol: 'ADAUSDT',
      side: 'long',
      pnl: 31.00,
      pnlPercentage: 3.1,
      createdAt: new Date(Date.now() - 12 * 60 * 1000).toISOString(), // 12 minutes ago
    },
  ];

  return (
    <Card className="bg-binance-card border-binance-border">
      <CardHeader className="border-b border-binance-border">
        <CardTitle className="text-lg font-semibold" data-testid="text-recent-trades-title">
          Останні угоди
        </CardTitle>
      </CardHeader>
      <CardContent className="p-6">
        <div className="space-y-3">
          {trades.map((trade) => (
            <div 
              key={trade.id} 
              className="flex items-center justify-between p-3 bg-binance-bg rounded-lg"
              data-testid={`trade-${trade.id}`}
            >
              <div>
                <div className="font-medium" data-testid={`text-symbol-${trade.id}`}>
                  {trade.symbol}
                </div>
                <div 
                  className={`text-sm ${
                    (trade.pnl || 0) >= 0 ? 'text-binance-success' : 'text-binance-error'
                  }`}
                  data-testid={`text-side-${trade.id}`}
                >
                  {trade.side === 'long' ? 'Long' : 'Short'} {trade.pnlPercentage ? `${trade.pnlPercentage > 0 ? '+' : ''}${trade.pnlPercentage}%` : ''}
                </div>
              </div>
              <div className="text-right">
                <div 
                  className={`font-medium ${
                    (trade.pnl || 0) >= 0 ? 'text-binance-success' : 'text-binance-error'
                  }`}
                  data-testid={`text-pnl-${trade.id}`}
                >
                  {formatPnL(trade.pnl || 0)}
                </div>
                <div className="text-sm text-binance-text-muted" data-testid={`text-time-${trade.id}`}>
                  {formatTime(trade.createdAt)}
                </div>
              </div>
            </div>
          ))}
        </div>
        
        {tradingHistory.length === 0 && (
          <div className="text-center py-8 text-binance-text-muted" data-testid="text-no-trades">
            <p>Поки що немає угод. Запустіть бота для початку торгівлі.</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
