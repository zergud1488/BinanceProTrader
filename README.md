# BinanceProTrader - Institutional SMC Scalper Bot (Binance Futures Mainnet)

Autonomous High-Frequency Trading Bot powered by Smart Money Concepts (SMC), Volume Imbalance (FVG), Order Block Retest, and Macro Trend Alignment.

## Cloud Architecture (Render.com)
- **Runtime**: Python 3.11
- **Region**: Frankfurt (Germany)
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python -u src/live_paper_bot.py --scan_interval 20 --pos_interval 2.5 --max_hold 15`
- **Health Check**: Responds on port `PORT` at `/` and `/health`.

## Portfolio Parameters
- **Capital**: $100.00 USDT
- **Leverage**: 20x (Isolated)
- **Margin/Trade**: $10.00 (Notional $200.00)
- **Max Positions**: 3
- **Strategy**: SMC Baseline (NO BE)
- **Take Profit**: Dynamic 1.4x ATR (1.0% - 2.8%)
- **Stop Loss**: Dynamic 2.0x ATR (1.6% - 3.5%)
- **Timeout**: 15 minutes
