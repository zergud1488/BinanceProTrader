import { useAuth } from "@/hooks/useAuth";
import { Bot, Settings, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link, useLocation } from "wouter";

export default function Navigation() {
  const { isAuthenticated, user, isLoading } = useAuth();
  const [location] = useLocation();

  const isAdmin = user?.email === "mustek@example.com"; // Mock admin check

  return (
    <nav className="bg-binance-card border-b border-binance-border sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-4">
            <Link href="/" className="flex items-center" data-testid="link-home">
              <Bot className="text-binance-yellow w-8 h-8 mr-3" />
              <span className="font-bold text-xl text-binance-text">CryptoBot</span>
            </Link>
          </div>
          
          {!isLoading && (
            <>
              {!isAuthenticated ? (
                <div className="hidden md:flex items-center space-x-8">
                  <a href="#" className="text-binance-text hover:text-binance-yellow transition-colors" data-testid="link-home-nav">
                    Головна
                  </a>
                  <a href="#" className="text-binance-text-muted hover:text-binance-yellow transition-colors" data-testid="link-about">
                    Про нас
                  </a>
                  <a href="#" className="text-binance-text-muted hover:text-binance-yellow transition-colors" data-testid="link-features">
                    Можливості
                  </a>
                </div>
              ) : (
                <div className="hidden md:flex items-center space-x-6">
                  <Link 
                    href="/" 
                    className={`text-sm font-medium transition-colors ${
                      location === "/" ? "text-binance-yellow" : "text-binance-text hover:text-binance-yellow"
                    }`}
                    data-testid="link-dashboard"
                  >
                    Дашборд
                  </Link>
                  {isAdmin && (
                    <Link 
                      href="/constructor" 
                      className={`text-sm font-medium transition-colors ${
                        location === "/constructor" ? "text-binance-yellow" : "text-binance-text hover:text-binance-yellow"
                      }`}
                      data-testid="link-constructor"
                    >
                      Конструктор
                    </Link>
                  )}
                </div>
              )}
              
              <div className="flex items-center space-x-4">
                {!isAuthenticated ? (
                  <>
                    <Button 
                      variant="outline" 
                      className="border-binance-yellow text-binance-yellow hover:bg-binance-yellow hover:text-binance-bg"
                      onClick={() => window.location.href = "/api/login"}
                      data-testid="button-login"
                    >
                      Увійти
                    </Button>
                    <Button 
                      className="bg-binance-yellow text-binance-bg hover:bg-binance-yellow-hover"
                      onClick={() => window.location.href = "/api/login"}
                      data-testid="button-register"
                    >
                      Реєстрація
                    </Button>
                  </>
                ) : (
                  <>
                    <div className="hidden md:flex items-center space-x-3" data-testid="text-user-info">
                      <div className="w-8 h-8 bg-binance-yellow rounded-full flex items-center justify-center">
                        <span className="text-binance-bg text-sm font-medium">
                          {user?.firstName?.charAt(0) || user?.email?.charAt(0) || 'U'}
                        </span>
                      </div>
                      <div className="text-sm">
                        <div className="text-binance-text font-medium">
                          {user?.firstName || user?.email || 'Користувач'}
                        </div>
                        {isAdmin && (
                          <div className="text-binance-text-muted text-xs">Адміністратор</div>
                        )}
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="border-binance-error text-binance-error hover:bg-binance-error hover:text-white"
                      onClick={() => window.location.href = "/api/logout"}
                      data-testid="button-logout"
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      Вийти
                    </Button>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
