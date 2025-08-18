import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { isUnauthorizedError } from "@/lib/authUtils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Save, Info } from "lucide-react";

export default function TradingConfig() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  
  const [config, setConfig] = useState({
    binanceApiKey: '',
    binanceSecretKey: '',
    telegramBotToken: '',
    telegramChatId: '',
    candleChangePercent: 2.5,
    positionSize: 100,
    stopLoss: 2.0,
    takeProfit: 4.0,
    trailingStop: 1.5,
    leverage: 20,
  });

  const { data: tradingConfig, isLoading } = useQuery({
    queryKey: ['/api/trading-config'],
    retry: false,
  });

  useEffect(() => {
    if (tradingConfig) {
      setConfig({
        binanceApiKey: tradingConfig.binanceApiKey || '',
        binanceSecretKey: tradingConfig.binanceSecretKey || '',
        telegramBotToken: tradingConfig.telegramBotToken || '',
        telegramChatId: tradingConfig.telegramChatId || '',
        candleChangePercent: tradingConfig.candleChangePercent || 2.5,
        positionSize: tradingConfig.positionSize || 100,
        stopLoss: tradingConfig.stopLoss || 2.0,
        takeProfit: tradingConfig.takeProfit || 4.0,
        trailingStop: tradingConfig.trailingStop || 1.5,
        leverage: tradingConfig.leverage || 20,
      });
    }
  }, [tradingConfig]);

  const saveMutation = useMutation({
    mutationFn: async (configData: typeof config) => {
      const response = await apiRequest('POST', '/api/trading-config', configData);
      return response.json();
    },
    onSuccess: () => {
      toast({
        title: "Успіх",
        description: "Налаштування збережено успішно",
      });
      queryClient.invalidateQueries({ queryKey: ['/api/trading-config'] });
    },
    onError: (error) => {
      if (isUnauthorizedError(error as Error)) {
        toast({
          title: "Неавторизовано",
          description: "Ви вийшли з системи. Перенаправлення...",
          variant: "destructive",
        });
        setTimeout(() => {
          window.location.href = "/api/login";
        }, 500);
        return;
      }
      toast({
        title: "Помилка",
        description: "Не вдалося зберегти налаштування",
        variant: "destructive",
      });
    },
  });

  const handleSave = () => {
    saveMutation.mutate(config);
  };

  const handleInputChange = (field: string, value: string | number) => {
    setConfig(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  if (isLoading) {
    return (
      <Card className="bg-binance-card border-binance-border">
        <CardContent className="p-6">
          <div className="animate-pulse space-y-4">
            {[1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-binance-bg rounded"></div>
                <div className="h-10 bg-binance-bg rounded"></div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-binance-card border-binance-border">
      <CardHeader className="border-b border-binance-border">
        <CardTitle className="text-xl font-semibold" data-testid="text-trading-config-title">
          Налаштування торгівлі
        </CardTitle>
      </CardHeader>
      
      <CardContent className="p-6 space-y-6">
        {/* API Configuration */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-binance-yellow" data-testid="text-api-config-title">
            API Конфігурація
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="block text-sm font-medium mb-2">
                Binance API Key
                <span className="text-binance-text-muted text-xs ml-2">Потрібен для торгівлі</span>
              </Label>
              <Input
                type="password"
                value={config.binanceApiKey}
                onChange={(e) => handleInputChange('binanceApiKey', e.target.value)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                placeholder="Введіть API ключ"
                data-testid="input-binance-api-key"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Binance Secret Key
                <span className="text-binance-text-muted text-xs ml-2">Секретний ключ</span>
              </Label>
              <Input
                type="password"
                value={config.binanceSecretKey}
                onChange={(e) => handleInputChange('binanceSecretKey', e.target.value)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                placeholder="Введіть секретний ключ"
                data-testid="input-binance-secret-key"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Telegram Bot Token
                <span className="text-binance-text-muted text-xs ml-2">Для сповіщень</span>
              </Label>
              <Input
                type="password"
                value={config.telegramBotToken}
                onChange={(e) => handleInputChange('telegramBotToken', e.target.value)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                placeholder="Введіть bot token"
                data-testid="input-telegram-bot-token"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Telegram Chat ID
                <span className="text-binance-text-muted text-xs ml-2">ID чату для сповіщень</span>
              </Label>
              <Input
                type="text"
                value={config.telegramChatId}
                onChange={(e) => handleInputChange('telegramChatId', e.target.value)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                placeholder="Введіть chat ID"
                data-testid="input-telegram-chat-id"
              />
            </div>
          </div>
        </div>

        {/* Trading Parameters */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-binance-yellow" data-testid="text-trading-params-title">
            Параметри торгівлі
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <Label className="block text-sm font-medium mb-2">
                Процент зміни свічки (%)
                <span className="text-binance-text-muted text-xs ml-2">Мінімальна зміна для входу</span>
              </Label>
              <Input
                type="number"
                value={config.candleChangePercent}
                onChange={(e) => handleInputChange('candleChangePercent', parseFloat(e.target.value) || 0)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                step="0.1"
                data-testid="input-candle-change-percent"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Розмір позиції (USDT)
                <span className="text-binance-text-muted text-xs ml-2">Розмір кожної угоди</span>
              </Label>
              <Input
                type="number"
                value={config.positionSize}
                onChange={(e) => handleInputChange('positionSize', parseFloat(e.target.value) || 0)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                data-testid="input-position-size"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Stop Loss (%)
                <span className="text-binance-text-muted text-xs ml-2">Максимальний збиток</span>
              </Label>
              <Input
                type="number"
                value={config.stopLoss}
                onChange={(e) => handleInputChange('stopLoss', parseFloat(e.target.value) || 0)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                step="0.1"
                data-testid="input-stop-loss"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Take Profit (%)
                <span className="text-binance-text-muted text-xs ml-2">Цільовий прибуток</span>
              </Label>
              <Input
                type="number"
                value={config.takeProfit}
                onChange={(e) => handleInputChange('takeProfit', parseFloat(e.target.value) || 0)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                step="0.1"
                data-testid="input-take-profit"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Trailing Stop (%)
                <span className="text-binance-text-muted text-xs ml-2">Динамічний стоп</span>
              </Label>
              <Input
                type="number"
                value={config.trailingStop}
                onChange={(e) => handleInputChange('trailingStop', parseFloat(e.target.value) || 0)}
                className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                step="0.1"
                data-testid="input-trailing-stop"
              />
            </div>
            <div>
              <Label className="block text-sm font-medium mb-2">
                Кредитне плече
                <span className="text-binance-text-muted text-xs ml-2">Множник позиції</span>
              </Label>
              <Select
                value={config.leverage.toString()}
                onValueChange={(value) => handleInputChange('leverage', parseInt(value))}
              >
                <SelectTrigger className="bg-binance-bg border-binance-border focus:border-binance-yellow" data-testid="select-leverage">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-binance-card border-binance-border">
                  <SelectItem value="5">5x</SelectItem>
                  <SelectItem value="10">10x</SelectItem>
                  <SelectItem value="20">20x</SelectItem>
                  <SelectItem value="50">50x</SelectItem>
                  <SelectItem value="100">100x</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </div>

        {/* Trading Logic */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-binance-yellow" data-testid="text-trading-logic-title">
            Логіка торгівлі
          </h3>
          <div className="bg-binance-bg rounded-lg p-4 border border-binance-border">
            <div className="flex items-center space-x-3">
              <Info className="text-binance-yellow w-5 h-5" />
              <p className="text-sm text-binance-text-muted" data-testid="text-trading-strategy">
                <strong>Стратегія:</strong> Якщо свічка лонгова (зростання ≥ установленого %) → відкриваємо шорт. 
                Якщо свічка шортова (падіння ≥ установленого %) → відкриваємо лонг.
              </p>
            </div>
          </div>
        </div>

        {/* Save Configuration */}
        <div className="flex justify-end">
          <Button 
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="bg-binance-success text-white hover:bg-green-600"
            data-testid="button-save-configuration"
          >
            <Save className="w-4 h-4 mr-2" />
            {saveMutation.isPending ? 'Збереження...' : 'Зберегти налаштування'}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
