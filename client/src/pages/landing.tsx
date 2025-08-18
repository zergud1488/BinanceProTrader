import Navigation from "@/components/navigation";
import { Bot, ChartLine, Shield, MessageCircle } from "lucide-react";

export default function Landing() {
  return (
    <div className="min-h-screen bg-binance-bg text-binance-text font-inter">
      <Navigation />
      
      {/* Hero Section */}
      <section className="py-20 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <h1 className="text-5xl md:text-6xl font-bold mb-8 leading-tight">
            Автоматична торгівля на{" "}
            <span className="text-binance-yellow">Binance</span>
          </h1>
          <p className="text-xl text-binance-text-muted mb-12 max-w-3xl mx-auto leading-relaxed">
            Професійна платформа для автоматичної торгівлі криптовалютами з підключенням через Binance API. 
            Налаштовуйте параметри, керуйте ризиками та отримуйте прибуток 24/7.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <button 
              onClick={() => window.location.href = "/api/login"}
              className="bg-binance-yellow text-binance-bg px-8 py-4 rounded-lg font-semibold text-lg hover:bg-binance-yellow-hover transition-colors w-full sm:w-auto"
              data-testid="button-get-started"
            >
              Розпочати торгівлю
            </button>
            <button 
              className="border border-binance-yellow text-binance-yellow px-8 py-4 rounded-lg font-semibold text-lg hover:bg-binance-yellow hover:text-binance-bg transition-all duration-200 w-full sm:w-auto"
              data-testid="button-demo"
            >
              Дивитися демо
            </button>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-4xl font-bold text-center mb-16" data-testid="text-features-title">
            Ключові можливості
          </h2>
          <div className="grid md:grid-cols-3 gap-8">
            {/* Feature 1 */}
            <div className="bg-binance-card rounded-xl p-8 border border-binance-border hover:border-binance-yellow transition-colors">
              <div className="text-binance-yellow text-3xl mb-4">
                <ChartLine className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-semibold mb-4" data-testid="text-feature-1-title">
                Автоматична торгівля
              </h3>
              <p className="text-binance-text-muted" data-testid="text-feature-1-description">
                Налаштовуйте параметри торгівлі та дозвольте боту працювати за вас. Система аналізує свічки та відкриває позиції згідно з вашими умовами.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="bg-binance-card rounded-xl p-8 border border-binance-border hover:border-binance-yellow transition-colors">
              <div className="text-binance-yellow text-3xl mb-4">
                <Shield className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-semibold mb-4" data-testid="text-feature-2-title">
                Риск-менеджмент
              </h3>
              <p className="text-binance-text-muted" data-testid="text-feature-2-description">
                Автоматичне встановлення Stop Loss, Take Profit та Trailing Stop для всіх відкритих позицій. Захистіть свій капітал.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="bg-binance-card rounded-xl p-8 border border-binance-border hover:border-binance-yellow transition-colors">
              <div className="text-binance-yellow text-3xl mb-4">
                <MessageCircle className="w-8 h-8" />
              </div>
              <h3 className="text-xl font-semibold mb-4" data-testid="text-feature-3-title">
                Telegram сповіщення
              </h3>
              <p className="text-binance-text-muted" data-testid="text-feature-3-description">
                Отримуйте детальні сповіщення про всі операції: відкриття/закриття позицій, профіт, стоплоси та поточний баланс.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Statistics Section */}
      <section className="py-16 px-4 bg-binance-card">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="text-3xl font-bold mb-12" data-testid="text-stats-title">
            Статистика платформи
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <div>
              <div className="text-3xl font-bold text-binance-yellow mb-2" data-testid="text-stat-users">
                1,247
              </div>
              <div className="text-binance-text-muted">Активних користувачів</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-binance-success mb-2" data-testid="text-stat-trades">
                89,432
              </div>
              <div className="text-binance-text-muted">Виконаних угод</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-binance-yellow mb-2" data-testid="text-stat-winrate">
                73.5%
              </div>
              <div className="text-binance-text-muted">Win Rate</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-binance-success mb-2" data-testid="text-stat-profit">
                +2.4M
              </div>
              <div className="text-binance-text-muted">USDT прибуток</div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
