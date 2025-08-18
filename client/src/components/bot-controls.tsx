import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import { useToast } from "@/hooks/use-toast";
import { isUnauthorizedError } from "@/lib/authUtils";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Play, Shield, Square } from "lucide-react";

export default function BotControls() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: botStatus, isLoading } = useQuery({
    queryKey: ['/api/bot-status'],
    retry: false,
  });

  const updateStatusMutation = useMutation({
    mutationFn: async (statusData: { tradingBotActive?: boolean; riskManagementActive?: boolean }) => {
      const response = await apiRequest('POST', '/api/bot-status', statusData);
      return response.json();
    },
    onSuccess: (data, variables) => {
      const actionMessages = {
        tradingBot: variables.tradingBotActive ? "Торговий бот запущено!" : "Торговий бот зупинено!",
        riskManagement: variables.riskManagementActive ? "Система риск-менеджменту запущена!" : "Система риск-менеджменту зупинена!",
        both: "Всі боти зупинено!",
      };

      let message = "";
      if (variables.tradingBotActive !== undefined && variables.riskManagementActive === undefined) {
        message = actionMessages.tradingBot;
      } else if (variables.riskManagementActive !== undefined && variables.tradingBotActive === undefined) {
        message = actionMessages.riskManagement;
      } else if (variables.tradingBotActive === false && variables.riskManagementActive === false) {
        message = actionMessages.both;
      }

      toast({
        title: "Успіх",
        description: message,
      });
      queryClient.invalidateQueries({ queryKey: ['/api/bot-status'] });
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
        description: "Не вдалося оновити статус бота",
        variant: "destructive",
      });
    },
  });

  const handleStartTradingBot = () => {
    updateStatusMutation.mutate({
      tradingBotActive: true,
      riskManagementActive: botStatus?.riskManagementActive || false,
    });
  };

  const handleStartRiskManagement = () => {
    updateStatusMutation.mutate({
      tradingBotActive: botStatus?.tradingBotActive || false,
      riskManagementActive: true,
    });
  };

  const handleStopAllBots = () => {
    updateStatusMutation.mutate({
      tradingBotActive: false,
      riskManagementActive: false,
    });
  };

  const tradingBotActive = botStatus?.tradingBotActive || false;
  const riskManagementActive = botStatus?.riskManagementActive || false;

  return (
    <>
      {/* Bot Controls */}
      <Card className="bg-binance-card border-binance-border">
        <CardHeader className="border-b border-binance-border">
          <CardTitle className="text-lg font-semibold" data-testid="text-bot-controls-title">
            Керування ботом
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <Button
            onClick={handleStartTradingBot}
            disabled={updateStatusMutation.isPending || tradingBotActive}
            className="w-full bg-binance-success text-white hover:bg-green-600 disabled:opacity-50"
            data-testid="button-start-trading-bot"
          >
            <Play className="w-4 h-4 mr-2" />
            {tradingBotActive ? 'Торговий бот активний' : 'Запустити торгового бота'}
          </Button>
          
          <Button
            onClick={handleStartRiskManagement}
            disabled={updateStatusMutation.isPending || riskManagementActive}
            className="w-full bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
            data-testid="button-start-risk-management"
          >
            <Shield className="w-4 h-4 mr-2" />
            {riskManagementActive ? 'Риск-менеджмент активний' : 'Запустити риск-менеджмент'}
          </Button>
          
          <Button
            onClick={handleStopAllBots}
            disabled={updateStatusMutation.isPending || (!tradingBotActive && !riskManagementActive)}
            className="w-full bg-binance-error text-white hover:bg-red-600 disabled:opacity-50"
            data-testid="button-stop-all-bots"
          >
            <Square className="w-4 h-4 mr-2" />
            Зупинити всі боти
          </Button>
        </CardContent>
      </Card>

      {/* Bot Status */}
      <Card className="bg-binance-card border-binance-border">
        <CardHeader className="border-b border-binance-border">
          <CardTitle className="text-lg font-semibold" data-testid="text-bot-status-title">
            Статус ботів
          </CardTitle>
        </CardHeader>
        <CardContent className="p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div 
                className={`w-3 h-3 rounded-full ${
                  tradingBotActive ? 'bg-binance-success' : 'bg-binance-error'
                }`}
                data-testid="indicator-trading-bot-status"
              />
              <span>Торговий бот</span>
            </div>
            <span className="text-sm text-binance-text-muted" data-testid="text-trading-bot-status">
              {tradingBotActive ? 'Активний' : 'Зупинено'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div 
                className={`w-3 h-3 rounded-full ${
                  riskManagementActive ? 'bg-binance-success' : 'bg-binance-error'
                }`}
                data-testid="indicator-risk-management-status"
              />
              <span>Риск-менеджмент</span>
            </div>
            <span className="text-sm text-binance-text-muted" data-testid="text-risk-management-status">
              {riskManagementActive ? 'Активний' : 'Зупинено'}
            </span>
          </div>
        </CardContent>
      </Card>
    </>
  );
}
