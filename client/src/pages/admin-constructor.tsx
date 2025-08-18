import { useEffect, useState } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useToast } from "@/hooks/use-toast";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiRequest } from "@/lib/queryClient";
import Navigation from "@/components/navigation";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Trash2, Plus, Save, TestTube, Rocket } from "lucide-react";

export default function AdminConstructor() {
  const { toast } = useToast();
  const { isAuthenticated, isLoading } = useAuth();
  const queryClient = useQueryClient();

  const [newParameter, setNewParameter] = useState({
    name: '',
    type: 'number',
    description: '',
    codeFragment: '',
  });

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

  const { data: customParameters = [], isLoading: parametersLoading } = useQuery({
    queryKey: ['/api/custom-parameters'],
  });

  const createParameterMutation = useMutation({
    mutationFn: async (parameterData: any) => {
      const response = await apiRequest('POST', '/api/custom-parameters', parameterData);
      return response.json();
    },
    onSuccess: () => {
      toast({
        title: "Успіх",
        description: "Новий параметр створено успішно",
      });
      setNewParameter({
        name: '',
        type: 'number',
        description: '',
        codeFragment: '',
      });
      queryClient.invalidateQueries({ queryKey: ['/api/custom-parameters'] });
    },
    onError: (error) => {
      toast({
        title: "Помилка",
        description: "Не вдалося створити параметр",
        variant: "destructive",
      });
    },
  });

  const handleCreateParameter = () => {
    if (!newParameter.name || !newParameter.description) {
      toast({
        title: "Помилка",
        description: "Заповніть всі обов'язкові поля",
        variant: "destructive",
      });
      return;
    }

    createParameterMutation.mutate(newParameter);
  };

  if (isLoading || parametersLoading) {
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
      
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Card className="bg-binance-card border-binance-border">
          <CardHeader className="border-b border-binance-border">
            <CardTitle className="text-2xl font-bold text-binance-yellow" data-testid="text-constructor-title">
              Режим конструктора
            </CardTitle>
            <p className="text-binance-text-muted mt-2" data-testid="text-constructor-description">
              Додавайте нові параметри та умови для торгового алгоритму
            </p>
          </CardHeader>
          
          <CardContent className="p-6 space-y-6">
            {/* Custom Parameter Addition */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" data-testid="text-new-parameter-title">
                Додати новий параметр
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <Label className="text-sm font-medium mb-2">Назва параметра</Label>
                  <Input
                    value={newParameter.name}
                    onChange={(e) => setNewParameter(prev => ({ ...prev, name: e.target.value }))}
                    className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                    placeholder="Наприклад: RSI Threshold"
                    data-testid="input-parameter-name"
                  />
                </div>
                <div>
                  <Label className="text-sm font-medium mb-2">Тип параметра</Label>
                  <Select 
                    value={newParameter.type} 
                    onValueChange={(value) => setNewParameter(prev => ({ ...prev, type: value }))}
                  >
                    <SelectTrigger className="bg-binance-bg border-binance-border focus:border-binance-yellow" data-testid="select-parameter-type">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-binance-card border-binance-border">
                      <SelectItem value="number">Число (Number)</SelectItem>
                      <SelectItem value="percentage">Відсоток (Percentage)</SelectItem>
                      <SelectItem value="boolean">Логічне значення (Boolean)</SelectItem>
                      <SelectItem value="select">Список вибору (Select)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label className="text-sm font-medium mb-2">Опис параметра</Label>
                <Textarea
                  value={newParameter.description}
                  onChange={(e) => setNewParameter(prev => ({ ...prev, description: e.target.value }))}
                  className="bg-binance-bg border-binance-border focus:border-binance-yellow"
                  rows={3}
                  placeholder="Детальний опис що робить цей параметр..."
                  data-testid="textarea-parameter-description"
                />
              </div>
            </div>

            {/* Code Fragment Addition */}
            <div className="space-y-4">
              <h3 className="text-lg font-medium" data-testid="text-code-fragment-title">
                Фрагмент коду
              </h3>
              <p className="text-sm text-binance-text-muted">
                Додайте JavaScript код, який буде виконуватись для цього параметра
              </p>
              <div className="relative">
                <Textarea
                  value={newParameter.codeFragment}
                  onChange={(e) => setNewParameter(prev => ({ ...prev, codeFragment: e.target.value }))}
                  className="bg-binance-bg border-binance-border focus:border-binance-yellow font-mono text-sm"
                  rows={10}
                  placeholder={`// Приклад коду для нового параметра
function checkCustomCondition(candleData, userParams) {
    const rsiValue = calculateRSI(candleData);
    return rsiValue > userParams.rsiThreshold;
}

// Додайте свій код тут...`}
                  data-testid="textarea-code-fragment"
                />
              </div>
            </div>

            {/* Save and Deploy */}
            <div className="flex justify-between items-center">
              <div className="space-x-4">
                <Button variant="secondary" data-testid="button-save-draft">
                  <Save className="w-4 h-4 mr-2" />
                  Зберегти як чернетку
                </Button>
                <Button variant="secondary" data-testid="button-test-code">
                  <TestTube className="w-4 h-4 mr-2" />
                  Тестувати код
                </Button>
              </div>
              <Button 
                onClick={handleCreateParameter}
                disabled={createParameterMutation.isPending}
                className="bg-binance-success hover:bg-green-600"
                data-testid="button-deploy-production"
              >
                <Rocket className="w-4 h-4 mr-2" />
                {createParameterMutation.isPending ? 'Створення...' : 'Розгорнути в продакшн'}
              </Button>
            </div>

            {/* Existing Parameters */}
            {customParameters.length > 0 && (
              <div className="space-y-4">
                <h3 className="text-lg font-medium" data-testid="text-existing-parameters-title">
                  Існуючі параметри
                </h3>
                <div className="space-y-3">
                  {customParameters.map((param: any) => (
                    <div key={param.id} className="bg-binance-bg rounded-lg p-4 border border-binance-border">
                      <div className="flex items-center justify-between">
                        <div>
                          <h4 className="font-medium" data-testid={`text-parameter-${param.id}-name`}>
                            {param.name}
                          </h4>
                          <p className="text-sm text-binance-text-muted" data-testid={`text-parameter-${param.id}-description`}>
                            {param.description}
                          </p>
                          <span className="text-xs bg-binance-yellow text-binance-bg px-2 py-1 rounded mt-2 inline-block">
                            {param.type}
                          </span>
                        </div>
                        <Button variant="destructive" size="sm" data-testid={`button-delete-parameter-${param.id}`}>
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
