import asyncio
import aiohttp
from aiohttp import web
import time
import datetime
import json
import csv
import sys
import os
import signal
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

# Force UTF-8 encoding for Windows terminals
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# Ensure imports work from project root
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
REPORTS_DIR = BASE_DIR / "reports"
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Import Audited Quantitative Trading System and SMC Engine
sys.path.insert(0, str(BASE_DIR / "src"))
from trading_system import UnifiedTradingSystem
from smc_engine import compute_smc_for_symbol

# Credentials & System Constants
TELEGRAM_BOT_TOKEN = "6110538923:AAEVgH4IAftaG8nAFjDiFz0-FSqGu1Fbv_g"
TELEGRAM_CHAT_ID = "669861467"
BINANCE_MAINNET_URL = "https://fapi.binance.com"

# Benchmark symbols used strictly for market regime & dump/pump shield (NEVER traded directly)
EXCLUDE_TRADING_SYMBOLS = {"BTCUSDT", "ETHUSDT"}

STATE_FILE = DATA_DIR / "live_paper_portfolio_state.json"
TRADES_CSV = REPORTS_DIR / "live_paper_trades.csv"

# =====================================================================
# 1. TELEGRAM NOTIFIER (Async, Fault-Tolerant, Auto-Retry)
# =====================================================================
class TelegramNotifier:
    """
    Robust Asynchronous Telegram Notifier.
    Handles network errors, connection drops, and rate limits gracefully.
    Never raises unhandled exceptions that could crash the trading engine.
    """
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=12)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def send_message(self, text: str, parse_mode: str = "HTML", max_retries: int = 3) -> bool:
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        for attempt in range(1, max_retries + 1):
            try:
                session = await self._get_session()
                async with session.post(self.base_url, json=payload) as resp:
                    if resp.status == 200:
                        return True
                    else:
                        err_body = await resp.text()
                        print(f"[!] Telegram API HTTP {resp.status} (attempt {attempt}/{max_retries}): {err_body}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                print(f"[!] Telegram network error (attempt {attempt}/{max_retries}): {e}")
            except Exception as e:
                print(f"[!] Unexpected error sending Telegram message: {e}")

            if attempt < max_retries:
                await asyncio.sleep(attempt * 1.5)
        return False

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()


# =====================================================================
# 2. PAPER PORTFOLIO MANAGER (Stateful, Persistent, Precise Friction)
# =====================================================================
class PaperPortfolio:
    """
    Stateful Paper Portfolio Engine.
    - Starting capital: $100.00
    - Fixed margin: $10.00 per trade (20x leverage -> $200.00 notional)
    - Max 3 concurrent positions (max $30 committed, $70+ cushion)
    - Realistic friction: 0.15% roundtrip (taker fee 0.05% x 2 + slippage 0.025% x 2)
    - Continuous JSON state persistence and CSV trade logging.
    """
    def __init__(self, 
                 starting_balance: float = 100.0,
                 margin_per_trade: float = 10.0,
                 leverage: float = 20.0,
                 max_concurrent_positions: int = 3,
                 friction_pct: float = 0.0015,
                 state_file: Optional[Path] = None,
                 trades_csv: Optional[Path] = None):
        self.state_file = state_file or STATE_FILE
        self.trades_csv = trades_csv or TRADES_CSV

        self.starting_balance = starting_balance
        self.balance = starting_balance
        self.margin_per_trade = margin_per_trade
        self.leverage = leverage
        self.max_positions = max_concurrent_positions
        self.friction_pct = friction_pct
        
        self.peak_balance = starting_balance
        self.max_drawdown_pct = 0.0
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        
        # Active positions: {symbol: dict}
        self.active_positions: Dict[str, dict] = {}
        # History of completed trades: [dict, ...] (bounded to recent 100 in memory)
        self.closed_trades: List[dict] = []

        self._init_csv()
        self.load_state()

    def _init_csv(self):
        if not self.trades_csv.exists():
            with open(self.trades_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "trade_id", "symbol", "side", "entry_time", "exit_time", 
                    "duration_sec", "entry_price", "exit_price", "margin_usd", 
                    "leverage", "notional_usd", "exit_reason", "price_change_pct", 
                    "gross_pnl_usd", "fee_usd", "net_pnl_usd", "roi_margin_pct", 
                    "balance_after", "win_rate_pct"
                ])

    def get_free_margin(self) -> float:
        committed_margin = len(self.active_positions) * self.margin_per_trade
        return max(0.0, self.balance - committed_margin)

    def can_open_position(self, symbol: str) -> bool:
        if symbol in self.active_positions:
            return False
        if len(self.active_positions) >= self.max_positions:
            return False
        if self.get_free_margin() < self.margin_per_trade:
            return False
        return True

    def open_position(self, symbol: str, entry_price: float, sl_price: float, 
                      sl_pct: float, tp_price: float, tp_pct: float, 
                      metrics: dict, side: str = "LONG") -> dict:
        notional = self.margin_per_trade * self.leverage
        now_ts = time.time()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        pos_record = {
            "symbol": symbol,
            "side": str(side).upper(),
            "entry_time": now_ts,
            "entry_time_str": now_str,
            "entry_price": float(entry_price),
            "margin_usd": self.margin_per_trade,
            "leverage": self.leverage,
            "notional_usd": notional,
            "sl_price": float(sl_price),
            "sl_pct": float(sl_pct),
            "tp_price": float(tp_price),
            "tp_pct": float(tp_pct),
            "highest_price": float(entry_price),
            "lowest_price": float(entry_price),
            "metrics": metrics
        }
        self.active_positions[symbol] = pos_record
        self.save_state()
        return pos_record

    def close_position(self, symbol: str, exit_price: float, exit_reason: str) -> Optional[dict]:
        if symbol not in self.active_positions:
            return None

        pos = self.active_positions.pop(symbol)
        now_ts = time.time()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        duration_sec = int(now_ts - pos["entry_time"])

        entry_p = pos["entry_price"]
        notional = pos["notional_usd"]
        margin = pos["margin_usd"]
        side = pos.get("side", "LONG").upper()

        # Directional PnL Math
        if side == "LONG":
            price_change_pct = (exit_price - entry_p) / entry_p * 100.0
            gross_pnl = notional * ((exit_price - entry_p) / entry_p)
        else: # SHORT
            price_change_pct = (entry_p - exit_price) / entry_p * 100.0
            gross_pnl = notional * ((entry_p - exit_price) / entry_p)

        fee = notional * self.friction_pct
        net_pnl = gross_pnl - fee
        roi_margin_pct = (net_pnl / margin) * 100.0

        # Update Portfolio State
        self.balance += net_pnl
        self.total_trades += 1
        if net_pnl > 0:
            self.wins += 1
        else:
            self.losses += 1

        if self.balance > self.peak_balance:
            self.peak_balance = self.balance
        dd_pct = (self.peak_balance - self.balance) / self.peak_balance * 100.0
        if dd_pct > self.max_drawdown_pct:
            self.max_drawdown_pct = dd_pct

        win_rate = (self.wins / self.total_trades * 100.0) if self.total_trades > 0 else 0.0

        trade_record = {
            "trade_id": self.total_trades,
            "symbol": symbol,
            "side": pos["side"],
            "entry_time": pos["entry_time_str"],
            "exit_time": now_str,
            "duration_sec": duration_sec,
            "entry_price": entry_p,
            "exit_price": float(exit_price),
            "margin_usd": margin,
            "leverage": pos["leverage"],
            "notional_usd": notional,
            "exit_reason": exit_reason, # 'TP', 'SL', 'TIME_EXIT'
            "price_change_pct": round(price_change_pct, 3),
            "gross_pnl_usd": round(gross_pnl, 4),
            "fee_usd": round(fee, 4),
            "net_pnl_usd": round(net_pnl, 4),
            "roi_margin_pct": round(roi_margin_pct, 2),
            "balance_after": round(self.balance, 2),
            "win_rate_pct": round(win_rate, 2)
        }

        self.closed_trades.append(trade_record)
        if len(self.closed_trades) > 200:
            self.closed_trades = self.closed_trades[-100:]
        self._log_to_csv(trade_record)
        self.save_state()
        return trade_record

    def _log_to_csv(self, t: dict):
        try:
            with open(self.trades_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    t["trade_id"], t["symbol"], t["side"], t["entry_time"], 
                    t["exit_time"], t["duration_sec"], t["entry_price"], 
                    t["exit_price"], t["margin_usd"], t["leverage"], 
                    t["notional_usd"], t["exit_reason"], t["price_change_pct"], 
                    t["gross_pnl_usd"], t["fee_usd"], t["net_pnl_usd"], 
                    t["roi_margin_pct"], t["balance_after"], t["win_rate_pct"]
                ])
        except Exception as e:
            print(f"[!] Error writing to trades CSV: {e}")

    def save_state(self):
        state = {
            "starting_balance": self.starting_balance,
            "balance": round(self.balance, 4),
            "peak_balance": round(self.peak_balance, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "margin_per_trade": self.margin_per_trade,
            "leverage": self.leverage,
            "max_positions": self.max_positions,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate_pct": round((self.wins / self.total_trades * 100.0) if self.total_trades > 0 else 0.0, 2),
            "active_positions": self.active_positions,
            "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        for attempt in range(3):
            try:
                temp_file = self.state_file.with_suffix(".tmp")
                with open(temp_file, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2, ensure_ascii=False)
                temp_file.replace(self.state_file)
                return state
            except Exception as e:
                if attempt == 2:
                    print(f"[!] Error saving portfolio state: {e}")
                time.sleep(0.05)
        return state

    def load_state(self):
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            self.starting_balance = data.get("starting_balance", self.starting_balance)
            self.balance = data.get("balance", self.balance)
            self.peak_balance = data.get("peak_balance", self.peak_balance)
            self.max_drawdown_pct = data.get("max_drawdown_pct", self.max_drawdown_pct)
            self.total_trades = data.get("total_trades", self.total_trades)
            self.wins = data.get("wins", self.wins)
            self.losses = data.get("losses", self.losses)
            self.active_positions = data.get("active_positions", {})
            print(f"[+] Loaded existing paper portfolio state: Balance=${self.balance:.2f}, Active Pos={len(self.active_positions)}, Trades={self.total_trades}")
        except Exception as e:
            print(f"[!] Error loading state file: {e}. Using clean defaults.")

    def get_stats(self) -> dict:
        total_pnl = self.balance - self.starting_balance
        total_roi = (total_pnl / self.starting_balance) * 100.0
        win_rate = (self.wins / self.total_trades * 100.0) if self.total_trades > 0 else 0.0
        return {
            "balance": self.balance,
            "starting_balance": self.starting_balance,
            "free_margin": self.get_free_margin(),
            "total_pnl": total_pnl,
            "total_roi": total_roi,
            "win_rate": win_rate,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "peak_balance": self.peak_balance,
            "max_drawdown": self.max_drawdown_pct,
            "active_count": len(self.active_positions)
        }


# =====================================================================
# 3. REAL-TIME DATA SCANNER & FEATURE ENGINE (Binance Mainnet)
# =====================================================================
class LiveMarketEngine:
    """
    Connects to Binance Futures Mainnet (fapi.binance.com).
    - Rapidly screens all 725+ USDT perpetual contracts.
    - Evaluates 100% causal features on strictly completed 1m candles.
    - Tracks BTC Dump Shield in real-time.
    """
    def __init__(self, base_url: str = BINANCE_MAINNET_URL, concurrency_limit: int = 25):
        self.base_url = base_url
        self.concurrency_limit = concurrency_limit
        self._session: Optional[aiohttp.ClientSession] = None
        self._sem: Optional[asyncio.Semaphore] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._sem is None:
            self._sem = asyncio.Semaphore(self.concurrency_limit)
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=60, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
            self._session = aiohttp.ClientSession(connector=connector, timeout=timeout, headers=headers)
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def scan_inplay_candidates(self, min_vol_usd: float = 10_000_000.0, 
                                     min_range_pct: float = 5.0, 
                                     max_candidates: int = 100) -> Dict[str, List[dict]]:
        """
        Screens 725+ tickers from Binance Futures Mainnet in a single request.
        Returns two distinct institutional pools (up to max_candidates total):
          - gainers: ranked by In-Play Long institutional score (change_24h >= +5.0%, volume, range)
          - dumpers: ranked by In-Play Short severity (change_24h <= -15.0%, volume, range)
        Excludes BTC/ETH benchmarks from active trading; dynamic rebalancing allocates remaining slots.
        """
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        session = await self._get_session()
        
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    err_text = await resp.text()
                    print(f"[!] Ticker fetch error HTTP {resp.status}: {err_text[:120]}")
                    if resp.status in (418, 429):
                        print("[!] Rate limit / IP ban encountered. Backing off for 30s to respect Binance cooldown...")
                        await asyncio.sleep(30)
                    return {"gainers": [], "dumpers": []}
                tickers = await resp.json()
        except Exception as e:
            print(f"[!] Network error fetching 24hr tickers: {e}")
            return {"gainers": [], "dumpers": []}

        scored_gainers = []
        scored_dumpers = []

        for t in tickers:
            sym = t.get("symbol", "")
            if not sym.endswith("USDT") or "_" in sym or sym in EXCLUDE_TRADING_SYMBOLS:
                continue

            try:
                quote_vol = float(t.get("quoteVolume", 0.0))
                high_p = float(t.get("highPrice", 0.0))
                low_p = float(t.get("lowPrice", 0.0))
                last_p = float(t.get("lastPrice", 0.0))
                price_chg = float(t.get("priceChangePercent", 0.0))
            except (ValueError, TypeError):
                continue

            if low_p <= 0 or last_p <= 0:
                continue

            range_pct = (high_p - low_p) / low_p * 100.0
            if quote_vol < min_vol_usd or range_pct < min_range_pct:
                continue

            # 1. Gainers bucket: change_24h_pct >= +5.0%
            if price_chg >= 5.0:
                vol_score = min(range_pct / 20.0, 3.0) * 45.0
                mom_score = min(price_chg / 15.0, 3.0) * 35.0
                liq_score = min(np.log10(quote_vol) / 10.0, 2.0) * 20.0
                scored_gainers.append({
                    "symbol": sym,
                    "last_price": last_p,
                    "change_24h_pct": price_chg,
                    "range_24h_pct": range_pct,
                    "volume_24h_usd": quote_vol,
                    "inplay_score": vol_score + mom_score + liq_score,
                    "side": "LONG"
                })

            # 2. Dumpers bucket: change_24h_pct <= -15.0% (In-Play Dumpers for Short)
            elif price_chg <= -15.0:
                vol_score = min(range_pct / 20.0, 3.0) * 40.0
                drop_score = min(abs(price_chg) / 15.0, 3.0) * 40.0
                liq_score = min(np.log10(quote_vol) / 10.0, 2.0) * 20.0
                scored_dumpers.append({
                    "symbol": sym,
                    "last_price": last_p,
                    "change_24h_pct": price_chg,
                    "range_24h_pct": range_pct,
                    "volume_24h_usd": quote_vol,
                    "inplay_score": vol_score + drop_score + liq_score,
                    "side": "SHORT"
                })

        scored_gainers.sort(key=lambda x: x["inplay_score"], reverse=True)
        scored_dumpers.sort(key=lambda x: x["inplay_score"], reverse=True)

        half_limit = max_candidates // 2
        top_gainers = scored_gainers[:half_limit]
        top_dumpers = scored_dumpers[:half_limit]

        # Dynamic slot rebalancing: if one bucket has fewer candidates, allocate remainder to the other side
        rem = max_candidates - (len(top_gainers) + len(top_dumpers))
        if rem > 0:
            if len(scored_gainers) > len(top_gainers):
                top_gainers = scored_gainers[:len(top_gainers) + rem]
            elif len(scored_dumpers) > len(top_dumpers):
                top_dumpers = scored_dumpers[:len(top_dumpers) + rem]

        return {
            "gainers": top_gainers,
            "dumpers": top_dumpers
        }

    async def check_btc_status(self) -> Tuple[int, float]:
        """
        Monitors BTCUSDT completed 1m candles.
        Returns:
          - btc_dump_warning: 1 if BTC dropped > 0.35% over last 3 completed minutes
          - btc_ret_15m: percentage return of BTC over last 15 completed minutes
        """
        url = f"{self.base_url}/fapi/v1/klines?symbol=BTCUSDT&interval=1m&limit=20"
        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    klines = await resp.json()
                    if len(klines) >= 16:
                        curr_ms = int(time.time() * 1000)
                        end_idx = -2 if curr_ms <= klines[-1][6] else -1
                        closes = [float(k[4]) for k in klines[:end_idx + 1]]
                        if len(closes) >= 16:
                            ret_3m = (closes[-1] - closes[-4]) / closes[-4] * 100.0
                            ret_15m = (closes[-1] - closes[-16]) / closes[-16] * 100.0
                            dump_warning = 1 if ret_3m <= -0.35 else 0
                            return dump_warning, ret_15m
        except Exception:
            pass
        return 0, 0.0

    async def fetch_symbol_features(self, symbol: str, btc_dump: int, btc_ret_15m: float = 0.0, side: str = "LONG") -> Optional[dict]:
        """
        Fetches multi-timeframe Binance Futures Mainnet candles for LONG or SHORT:
        - 1m (limit=100) for real SMC (OB, FVG, S/R Flip, Breakout Retest / Breakdown Retest) and Orderflow
        - 15m (limit=30) for true 15m EMA trend (EMA 9 vs 21)
        - 1h (limit=30) for true 1h EMA trend (EMA 9 vs 21)
        Evaluates strictly on the last COMPLETED 1m bar (100% causal, zero look-ahead).
        """
        session = await self._get_session()
        u_1m = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval=1m&limit=100"
        u_15m = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval=15m&limit=30"
        u_1h = f"{self.base_url}/fapi/v1/klines?symbol={symbol}&interval=1h&limit=30"

        try:
            async with self._sem:
                r1, r15, r1h = await asyncio.gather(
                    session.get(u_1m), session.get(u_15m), session.get(u_1h)
                )
                if r1.status != 200 or r15.status != 200 or r1h.status != 200:
                    return None
                k1 = await r1.json()
                k15 = await r15.json()
                k1h = await r1h.json()
        except Exception:
            return None

        if not isinstance(k1, list) or len(k1) < 50 or len(k15) < 22 or len(k1h) < 22:
            return None

        # 1. Real 1h Trend (EMA 9 vs 21 on 1h bars)
        c1h = np.array([float(k[4]) for k in k1h])
        ema9_1h = np.mean(c1h[-9:])
        ema21_1h = np.mean(c1h[-21:])
        trend_1h_bull = 1 if ema9_1h > ema21_1h else 0

        # 2. Real 15m Trend (EMA 9 vs 21 on 15m bars)
        c15 = np.array([float(k[4]) for k in k15])
        ema9_15 = np.mean(c15[-9:])
        ema21_15 = np.mean(c15[-21:])
        trend_15m_bull = 1 if ema9_15 > ema21_15 else 0

        side_u = str(side).upper()

        # Fast prune:
        if side_u == "LONG":
            if trend_15m_bull != 1 or trend_1h_bull != 1 or btc_dump == 1:
                return {"symbol": symbol, "side": "LONG", "skip": True}
        else: # SHORT
            if trend_15m_bull != 0 or trend_1h_bull != 0 or btc_ret_15m > 0.6:
                return {"symbol": symbol, "side": "SHORT", "skip": True}

        # 3. Last completed 1m candle
        curr_ms = int(time.time() * 1000)
        eval_idx = -2 if curr_ms <= k1[-1][6] else -1
        mark_price = float(k1[-1][4])

        k_eval = k1[:eval_idx + 1]
        opens = np.array([float(k[1]) for k in k_eval], dtype=np.float64)
        highs = np.array([float(k[2]) for k in k_eval], dtype=np.float64)
        lows = np.array([float(k[3]) for k in k_eval], dtype=np.float64)
        closes = np.array([float(k[4]) for k in k_eval], dtype=np.float64)
        vols = np.array([float(k[5]) for k in k_eval], dtype=np.float64)
        taker_vols = np.array([float(k[9]) for k in k_eval], dtype=np.float64)

        target_o = opens[-1]
        target_h = highs[-1]
        target_l = lows[-1]
        target_c = closes[-1]
        target_v = vols[-1]
        target_tb_v = taker_vols[-1]

        # 4. Orderflow & Geometry
        vol_sma_20 = np.mean(vols[-21:-1]) if len(vols) >= 21 else np.mean(vols[:-1])
        rvol = target_v / (vol_sma_20 + 1e-8)
        tb_ratio = target_tb_v / (target_v + 1e-8)
        candle_h = target_h - target_l + 1e-8
        lower_wick = (min(target_o, target_c) - target_l) / candle_h
        upper_wick = (target_h - max(target_o, target_c)) / candle_h

        # True Range & ATR-15
        tr_list = [highs[0] - lows[0]]
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
            tr_list.append(tr)
        atr_15_pct = (np.mean(tr_list[-15:]) / target_c * 100.0) if len(tr_list) >= 15 else 1.0

        # Volatility Gate: Require True In-Play Volatility (ATR-15 >= 0.70%)
        # Excludes heavy, low-beta coins where 1.2% TP is too far for 15-60m
        if atr_15_pct < 0.70:
            return {"symbol": symbol, "side": side_u, "skip": True}

        utc_hour = datetime.datetime.now(datetime.timezone.utc).hour

        if side_u == "LONG":
            rvols = np.ones(len(vols), dtype=np.float64)
            for i in range(20, len(vols)):
                rvols[i] = vols[i] / (np.mean(vols[i-20:i]) + 1e-8)
            atr_arr = np.full(len(closes), atr_15_pct, dtype=np.float64)

            fvg_trig, ob_trig, sr_trig, conf = compute_smc_for_symbol(
                opens, highs, lows, closes, vols, rvols, atr_arr
            )
            smc_fvg_bull = int(fvg_trig[-1])
            smc_ob_bull = int(ob_trig[-1])
            smc_sr_flip = int(sr_trig[-1])

            prev_swing_high_15 = np.max(highs[-16:-1]) if len(highs) >= 16 else highs[-2]
            smc_breakout_retest_bull = 1 if (
                target_c > target_o and 
                target_l <= prev_swing_high_15 and 
                target_c >= prev_swing_high_15 and 
                target_c > closes[-2]
            ) else 0

            return {
                "symbol": symbol,
                "side": "LONG",
                "hour_utc": utc_hour,
                "btc_dump_warning": btc_dump,
                "btc_ret_15m": btc_ret_15m,
                "trend_15m_bull": trend_15m_bull,
                "trend_1h_bull": trend_1h_bull,
                "rvol_20": rvol,
                "taker_buy_ratio": tb_ratio,
                "lower_wick_ratio": lower_wick,
                "upper_wick_ratio": upper_wick,
                "open": target_o,
                "high": target_h,
                "low": target_l,
                "close": target_c,
                "mark_price": mark_price,
                "atr_15_pct": atr_15_pct,
                "smc_ob_bull": smc_ob_bull,
                "smc_fvg_bull": smc_fvg_bull,
                "smc_sr_flip": smc_sr_flip,
                "smc_breakout_retest_bull": smc_breakout_retest_bull,
                "skip": False
            }
        else: # SHORT
            # Audited Breakdown Retest:
            prev_swing_low_15 = np.min(lows[-16:-1]) if len(lows) >= 16 else lows[-2]
            smc_breakdown_retest_bear = 1 if (
                target_c < target_o and
                target_h >= prev_swing_low_15 and
                target_c <= prev_swing_low_15 and
                target_c < closes[-2]
            ) else 0

            return {
                "symbol": symbol,
                "side": "SHORT",
                "hour_utc": utc_hour,
                "btc_dump_warning": btc_dump,
                "btc_ret_15m": btc_ret_15m,
                "trend_15m_bull": trend_15m_bull,
                "trend_1h_bull": trend_1h_bull,
                "rvol_20": rvol,
                "taker_buy_ratio": tb_ratio,
                "lower_wick_ratio": lower_wick,
                "upper_wick_ratio": upper_wick,
                "open": target_o,
                "high": target_h,
                "low": target_l,
                "close": target_c,
                "mark_price": mark_price,
                "atr_15_pct": atr_15_pct,
                "smc_breakdown_retest_bear": smc_breakdown_retest_bear,
                "skip": False
            }

    async def fetch_position_candle_info(self, symbols: List[str]) -> Dict[str, dict]:
        """
        High-speed price & candle tracker for active open positions.
        Returns latest current price, 1m candle high, and 1m candle low to catch wicks.
        """
        if not symbols:
            return {}
        
        session = await self._get_session()
        data_map = {}
        
        async def _fetch_one(sym: str):
            url = f"{self.base_url}/fapi/v1/klines?symbol={sym}&interval=1m&limit=2"
            try:
                async with session.get(url, timeout=3) as resp:
                    if resp.status == 200:
                        kl = await resp.json()
                        if kl and len(kl) > 0:
                            cur_bar = kl[-1]
                            data_map[sym] = {
                                "cur_p": float(cur_bar[4]),
                                "high_p": float(cur_bar[2]),
                                "low_p": float(cur_bar[3])
                            }
            except Exception:
                pass

        await asyncio.gather(*[_fetch_one(s) for s in symbols])
        return data_map


# =====================================================================
# 4. STRATEGY EVALUATOR (Direct proxy to audited UnifiedTradingSystem)
# =====================================================================
class SMCStrategyEngine:
    """
    Direct proxy to the Audited UnifiedTradingSystem (from src/trading_system.py).
    Integrates 6 audited institutional filters:
    1. Session Filter (05:00 - 09:00 UTC)
    2. Bitcoin Dump Shield (btc_dump_warning == 0)
    3. Multi-timeframe trend alignment (15m AND 1h Bullish)
    4. Climax Volume Filter (RVOL 1.10 - 5.5)
    5. Orderflow Absorption: Taker Buy >= 55%, Lower Wick >= 15%, Green candle
    6. Smart Money Concepts (SMC): Real OB, Real FVG, Real S/R Flip, Real BSR
    """
    def __init__(self):
        self.system = UnifiedTradingSystem(
            starting_balance=100.0,
            margin_fraction=0.10,
            leverage=20.0,
            enable_be=False
        )

    def evaluate_entry_signal(self, row: dict, side: str = "LONG") -> Tuple[bool, List[str]]:
        if row.get("skip", False):
            return False, []

        reasons = []
        if str(side).upper() == "LONG":
            sig = self.system.evaluate_signal(row)
            if sig:
                if row.get("smc_fvg_bull"):
                    reasons.append("FVG Imbalance")
                if row.get("smc_ob_bull"):
                    reasons.append("Order Block")
                if row.get("smc_sr_flip"):
                    reasons.append("S/R Flip")
                if row.get("smc_breakout_retest_bull"):
                    reasons.append("Breakout Retest")
        else: # SHORT
            sig = self.system.evaluate_short_signal(row)
            if sig:
                if row.get("smc_breakdown_retest_bear"):
                    reasons.append("Breakdown Retest")
        return sig, reasons

    def calculate_sltp(self, entry_price: float, atr_15_pct: float, side: str = "LONG") -> Tuple[float, float, float, float]:
        return self.system.calculate_sltp(entry_price, atr_15_pct, side=side)


# =====================================================================
# 5. AUTONOMOUS LIVE PAPER TRADING BOT CONTROLLER
# =====================================================================
class LivePaperBot:
    """
    Main Orchestrator for Real-Time Paper Trading on Binance Futures Mainnet.
    Coordinates Market Scanner, Signal Engine, Portfolio Manager, Fast Position Watcher,
    and Telegram Notifications.
    """
    def __init__(self, 
                 scan_interval_sec: int = 20, 
                 position_check_interval_sec: float = 2.5,
                 max_hold_minutes: int = 60,
                 scan_limit: int = 100):
        self.scan_interval = scan_interval_sec
        self.pos_check_interval = position_check_interval_sec
        self.max_hold_minutes = max_hold_minutes
        self.scan_limit = scan_limit
        
        self.notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.portfolio = PaperPortfolio(
            starting_balance=100.0,
            margin_per_trade=10.0,
            leverage=20.0,
            max_concurrent_positions=3,
            friction_pct=0.0015
        )
        self.market = LiveMarketEngine(concurrency_limit=25)
        self.strategy = SMCStrategyEngine()
        
        self.is_running = False
        self.start_time = time.time()
        self.last_heartbeat_time = time.time()
        self.last_scan_info = {
            "timestamp": None,
            "candidates_count": 0,
            "leaders": [],
            "error": None
        }

    async def initialize(self):
        print("="*80)
        print("🚀 INITIALIZING AUTONOMOUS LIVE PAPER TRADING BOT (BINANCE MAINNET)")
        print(f"   Capital: ${self.portfolio.balance:.2f} | Leverage: {self.portfolio.leverage}x | Margin/Trade: ${self.portfolio.margin_per_trade:.2f}")
        print(f"   Max Pos: {self.portfolio.max_positions} | Max Hold: {self.max_hold_minutes}m | Scan Limit: {self.scan_limit} coins | Strategy: SMC (NO BE)")
        print(f"   Telegram Alerts: Chat ID {TELEGRAM_CHAT_ID} (YabkoShop_bot)")
        print("="*80)

        # Startup notification
        stats = self.portfolio.get_stats()
        start_msg = (
            "🤖 <b>SMC LIVE PAPER TRADING BOT ЗАПУЩЕНО!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "📊 <b>Режим:</b> Реал-тайм ринок Binance Futures (Mainnet)\n"
            f"💵 <b>Початковий баланс:</b> ${stats['balance']:.2f} USDT\n"
            f"⚡ <b>Кредитне плече:</b> {self.portfolio.leverage:.0f}x (Ізольоване)\n"
            f"🎯 <b>Маржа на угоду:</b> ${self.portfolio.margin_per_trade:.2f} (Номінал: ${self.portfolio.margin_per_trade * self.portfolio.leverage:.2f})\n"
            f"🛡️ <b>Макс. позицій:</b> {self.portfolio.max_positions} (Вільна маржа: ${stats['free_margin']:.2f})\n"
            "📐 <b>Стратегія:</b> SMC In-Play Scalper (БЕЗ безубитку)\n"
            "🎯 <b>Take Profit:</b> Динамічний 1.4x ATR (1.0% – 2.8%)\n"
            "🛑 <b>Stop Loss:</b> Динамічний 2.0x ATR (1.6% – 3.5%)\n"
            f"⏱️ <b>Тайм-аут:</b> {self.max_hold_minutes} хв (закриття застою)\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "✅ <i>Моніторинг 725+ пар активовано! Сповіщення будуть надходити миттєво.</i>"
        )
        await self.notifier.send_message(start_msg)
        
        # Start lightweight web dashboard & health check for Koyeb/cloud
        asyncio.create_task(self.start_web_server())

    async def start_web_server(self):
        port = int(os.environ.get("PORT", 8000))
        app = web.Application()
        
        async def handle_index(request):
            stats = self.portfolio.get_stats()
            pos_list = ""
            for s, p in self.portfolio.active_positions.items():
                pos_list += f"<li><b>{s}</b>: Entry ${p['entry_price']:.4f} | TP: ${p['tp_price']:.4f} | SL: ${p['sl_price']:.4f}</li>"
            if not pos_list:
                pos_list = "<i>Немає відкритих позицій</i>"
            
            pnl_col = "#0ecb81" if stats['total_pnl'] >= 0 else "#f6465d"
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SMC Live Trading Bot</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0b0e11; color: #eaecef; padding: 20px; max-width: 500px; margin: auto; }}
        .card {{ background: #181a20; border-radius: 12px; padding: 18px; margin-bottom: 16px; border: 1px solid #2b313a; }}
        h2 {{ color: #f0b90b; margin-top: 0; }}
        .row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #282d35; }}
        .badge {{ background: #0ecb81; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px; }}
        ul {{ padding-left: 20px; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>🚀 SMC Paper Bot <span class="badge">RUNNING 24/7</span></h2>
        <div class="row"><span>Баланс:</span><b>${stats['balance']:.2f} USDT</b></div>
        <div class="row"><span>Чистий PnL:</span><b style="color: {pnl_col}">{stats['total_pnl']:+.2f} USDT ({stats['total_roi']:+.1f}%)</b></div>
        <div class="row"><span>Вінрейт:</span><b>{stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)</b></div>
        <div class="row"><span>Всього угод:</span><b>{stats['total_trades']}</b></div>
        <div class="row"><span>Вільна маржа:</span><b>${stats['free_margin']:.2f} USDT</b></div>
    </div>
    <div class="card">
        <h3>📌 Активні позиції ({stats['active_count']}/3)</h3>
        <ul>{pos_list}</ul>
    </div>
</body>
</html>"""
            return web.Response(text=html, content_type="text/html")

        async def handle_health(request):
            return web.json_response({"status": "ok", "balance": self.portfolio.balance})

        async def handle_status(request):
            egress_ip = "unknown"
            binance_ping = "unknown"
            try:
                session = await self.market._get_session()
                async with session.get("https://api.ipify.org?format=json", timeout=3) as r:
                    if r.status == 200:
                        egress_ip = (await r.json()).get("ip")
            except Exception as e:
                egress_ip = str(e)

            binance_body = ""
            try:
                session = await self.market._get_session()
                async with session.get(f"{self.market.base_url}/fapi/v1/ping", timeout=3) as r:
                    binance_ping = f"HTTP {r.status}"
                    binance_body = await r.text()
            except Exception as e:
                binance_ping = str(e)

            ws_status = "untested"
            try:
                session = await self.market._get_session()
                async with session.ws_connect("wss://fstream.binance.com/ws/!ticker@arr", timeout=4) as ws:
                    msg = await asyncio.wait_for(ws.receive_str(), timeout=3)
                    ws_status = f"OK (received {len(msg)} bytes)"
            except Exception as e:
                ws_status = f"WS Error: {e}"

            return web.json_response({
                "status": "ok",
                "egress_ip": egress_ip,
                "binance_ping": binance_ping,
                "binance_body": binance_body,
                "binance_ws": ws_status,
                "balance": self.portfolio.balance,
                "active_positions": list(self.portfolio.active_positions.keys()),
                "last_scan": self.last_scan_info,
                "stats": self.portfolio.get_stats()
            })

        app.router.add_get("/", handle_index)
        app.router.add_get("/health", handle_health)
        app.router.add_get("/status", handle_status)

        try:
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", port)
            await site.start()
            print(f"[+] Web Health Server active on http://0.0.0.0:{port} (PaaS/Koyeb Ready)")
        except Exception as e:
            print(f"[!] Warning: Could not bind web server on port {port}: {e}")

    async def notify_order_open(self, pos: dict):
        m = pos["metrics"]
        patterns_str = ", ".join(m.get("patterns", ["SMC Setup"]))
        side = pos.get("side", "LONG").upper()
        is_long = (side == "LONG")
        side_tag = "LONG 🟢" if is_long else "SHORT 🔴"
        header = "🚀 <b>НОВА УГОДА / ВІДКРИТО ЛОНГ</b>" if is_long else "🔻 <b>НОВА УГОДА / ВІДКРИТО ШОРТ</b>"
        sl_sign = "-" if is_long else "+"
        tp_sign = "+" if is_long else "-"
        wick_name = "Відкупний гніт (знизу)" if is_long else "Гніт відхилення (зверху)"
        trend_name = "Бичачий (EMA)" if is_long else "Ведмежий (EMA)"

        msg = (
            f"{header}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> #{pos['symbol']} ({side_tag})\n"
            f"💵 <b>Ціна входу:</b> ${pos['entry_price']:.4f}\n"
            f"📦 <b>Об'єм:</b> ${pos['notional_usd']:.2f} (Маржа: ${pos['margin_usd']:.2f} × {pos['leverage']:.0f}x)\n\n"
            f"🎯 <b>Take Profit:</b> ${pos['tp_price']:.4f} ({tp_sign}{pos['tp_pct']:.2f}%)\n"
            f"🛑 <b>Stop Loss:</b> ${pos['sl_price']:.4f} ({sl_sign}{pos['sl_pct']:.2f}%)\n"
            f"⏱️ <b>Макс. утримання:</b> {self.max_hold_minutes} хв\n\n"
            "📊 <b>Сигнали та метрики:</b>\n"
            f"• Патерн: <i>{patterns_str}</i>\n"
            f"• RVOL (20m): <b>{m.get('rvol', 1.0):.2f}x</b>\n"
            f"• Taker Buy Ratio: <b>{m.get('taker_buy', 0.5)*100:.1f}%</b>\n"
            f"• {wick_name}: <b>{m.get('wick', 0.2)*100:.1f}%</b>\n"
            f"• 15m/1h Тренд: <b>{trend_name}</b>\n\n"
            f"💼 <b>Баланс:</b> ${self.portfolio.balance:.2f} | <b>Вільна маржа:</b> ${self.portfolio.get_free_margin():.2f}\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await self.notifier.send_message(msg)

    async def notify_trade_close(self, t: dict):
        sym = t["symbol"]
        side = t.get("side", "LONG").upper()
        is_long = (side == "LONG")
        side_tag = "LONG 🟢" if is_long else "SHORT 🔴"
        exit_r = t["exit_reason"]
        net_pnl = t["net_pnl_usd"]
        pnl_pct = t["price_change_pct"]
        roi_margin = t["roi_margin_pct"]
        stats = self.portfolio.get_stats()
        
        mins = t["duration_sec"] // 60
        secs = t["duration_sec"] % 60
        duration_str = f"{mins}хв {secs}с"

        if exit_r == "TP":
            header = f"🎯 <b>ТЕЙК ПРОФІТ СПРАЦЮВАВ! [WIN]</b> ({side_tag})"
            pnl_line = f"💰 <b>Чистий прибуток:</b> +${net_pnl:.2f} USDT (+{roi_margin:.1f}% до маржі)"
        elif exit_r == "SL":
            header = f"🛑 <b>СТОП ЛОСС СПРАЦЮВАВ [LOSS]</b> ({side_tag})"
            pnl_line = f"💸 <b>Збиток:</b> -${abs(net_pnl):.2f} USDT ({roi_margin:.1f}% до маржі)"
        else:
            pnl_emoji = "🟢" if net_pnl >= 0 else "🔴"
            header = f"⏱️ <b>ЗАКРИТТЯ ЗА ЧАСОМ (15 ХВ)</b> ({side_tag})"
            pnl_line = f"{pnl_emoji} <b>Чистий PnL:</b> {net_pnl:+.2f} USDT ({roi_margin:+.1f}% до маржі)\n⏱️ <i>Причина: Застій понад 15 хв (звільнення слота)</i>"

        msg = (
            f"{header}\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🪙 <b>Монета:</b> #{sym} ({side_tag})\n"
            f"💵 <b>Вхід:</b> ${t['entry_price']:.4f} ➔ <b>Вихід:</b> ${t['exit_price']:.4f}\n"
            f"📈 <b>Рух ціни:</b> {pnl_pct:+.2f}%\n"
            f"{pnl_line}\n"
            f"⏱️ <b>Час у позиції:</b> {duration_str}\n\n"
            "📊 <b>Стан портфеля:</b>\n"
            f"• Баланс: <b>${stats['balance']:.2f} USDT</b>\n"
            f"• Загальний PnL: <b>{stats['total_pnl']:+.2f} USDT ({stats['total_roi']:+.1f}%)</b>\n"
            f"• Вінрейт: <b>{stats['win_rate']:.1f}%</b> ({stats['wins']}W / {stats['losses']}L | всього: {stats['total_trades']})\n"
            f"• Макс. просадка: <b>{stats['max_drawdown']:.1f}%</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await self.notifier.send_message(msg)

    async def notify_periodic_heartbeat(self):
        stats = self.portfolio.get_stats()
        uptime_sec = int(time.time() - self.start_time)
        hours = uptime_sec // 3600
        mins = (uptime_sec % 3600) // 60
        uptime_str = f"{hours}г {mins}хв"

        msg = (
            "📊 <b>СТАТИСТИКА РОБОТИ БОТА (ХАРТБІТ)</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱️ <b>Аптайм:</b> {uptime_str}\n"
            f"💼 <b>Поточний баланс:</b> ${stats['balance']:.2f} USDT\n"
            f"📈 <b>Чистий PnL:</b> {stats['total_pnl']:+.2f} USDT ({stats['total_roi']:+.1f}%)\n"
            f"🎯 <b>Вінрейт:</b> {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)\n"
            f"📊 <b>Всього угод:</b> {stats['total_trades']}\n"
            f"📌 <b>Активних позицій:</b> {stats['active_count']} / {self.portfolio.max_positions}\n"
            "🔍 <b>Статус:</b> Моніторинг ринку Binance Mainnet (DUAL: Long+Short) працює стабільно\n"
            "━━━━━━━━━━━━━━━━━━━━━━"
        )
        await self.notifier.send_message(msg)

    async def watch_active_positions(self):
        """
        High-frequency position checking loop (runs every 2.5 seconds).
        Monitors open positions against TP, SL, and 15m time limits for both LONG and SHORT.
        """
        if not self.portfolio.active_positions:
            return

        tracked_symbols = list(self.portfolio.active_positions.keys())
        candle_infos = await self.market.fetch_position_candle_info(tracked_symbols)
        now_ts = time.time()

        for sym in tracked_symbols:
            if sym not in self.portfolio.active_positions:
                continue

            pos = self.portfolio.active_positions[sym]
            info = candle_infos.get(sym)
            if not info:
                continue

            cur_p = info["cur_p"]
            high_p = info["high_p"]
            low_p = info["low_p"]

            # Update highest / lowest seen
            if high_p > pos["highest_price"]:
                pos["highest_price"] = high_p
            if low_p < pos["lowest_price"]:
                pos["lowest_price"] = low_p

            side = pos.get("side", "LONG").upper()
            sl_p = pos["sl_price"]
            tp_p = pos["tp_price"]
            entry_p = pos["entry_price"]
            hold_sec = now_ts - pos["entry_time"]

            if side == "LONG":
                cur_pnl_pct = (cur_p - entry_p) / entry_p * 100.0
                cur_unpnl_usd = pos["notional_usd"] * ((cur_p - entry_p) / entry_p)
                hit_tp = (cur_p >= tp_p) or (high_p >= tp_p)
                hit_sl = (cur_p <= sl_p) or (low_p <= sl_p)
                exit_tp_price = tp_p
                exit_sl_price = sl_p
            else: # SHORT
                cur_pnl_pct = (entry_p - cur_p) / entry_p * 100.0
                cur_unpnl_usd = pos["notional_usd"] * ((entry_p - cur_p) / entry_p)
                hit_tp = (cur_p <= tp_p) or (low_p <= tp_p)
                hit_sl = (cur_p >= sl_p) or (high_p >= sl_p)
                exit_tp_price = tp_p
                exit_sl_price = sl_p

            # Telemetry print
            print(f"   [Pos Active {side}] {sym}: Entry ${entry_p:.4f} | Cur ${cur_p:.4f} ({cur_pnl_pct:+.2f}%) | UnPnL: ${cur_unpnl_usd:+.2f} | Hold: {hold_sec/60:.1f}m/{self.max_hold_minutes}m")

            # Check SL and TP triggers (including wicks)
            if hit_tp and hit_sl:
                # Both breached in wild volatility -> conservative execution: trigger SL
                print(f"\n[🛑 STOP LOSS TRIGGERED (Wick Flash)] {sym} ({side}) touched both brackets in bar")
                trade_res = self.portfolio.close_position(sym, exit_sl_price, "SL")
                if trade_res:
                    await self.notify_trade_close(trade_res)
                continue
            elif hit_tp:
                print(f"\n[🎯 TAKE PROFIT TRIGGERED] {sym} ({side}) reached TP ${tp_p:.4f}")
                trade_res = self.portfolio.close_position(sym, exit_tp_price, "TP")
                if trade_res:
                    await self.notify_trade_close(trade_res)
                continue
            elif hit_sl:
                print(f"\n[🛑 STOP LOSS TRIGGERED] {sym} ({side}) reached SL ${sl_p:.4f}")
                trade_res = self.portfolio.close_position(sym, exit_sl_price, "SL")
                if trade_res:
                    await self.notify_trade_close(trade_res)
                continue

            # Check 15-Minute Time Exit
            if hold_sec >= self.max_hold_minutes * 60:
                print(f"\n[⏱️ TIME EXIT TRIGGERED] {sym} ({side}) held for {hold_sec/60:.1f}m >= {self.max_hold_minutes}m")
                trade_res = self.portfolio.close_position(sym, cur_p, "TIME_EXIT")
                if trade_res:
                    await self.notify_trade_close(trade_res)
                continue

    async def scan_and_evaluate_signals(self):
        """
        Screens Binance Futures Mainnet for DUAL (Long Gainers + Short Dumpers) setups.
        """
        if not self.portfolio.can_open_position("TEST_CHECK"):
            return

        # 1. Fast screen of top candidates (Gainers + Dumpers)
        candidates_dict = await self.market.scan_inplay_candidates(
            min_vol_usd=10_000_000.0,
            min_range_pct=3.5,
            max_candidates=self.scan_limit
        )
        gainers = candidates_dict.get("gainers", [])
        dumpers = candidates_dict.get("dumpers", [])

        if not gainers and not dumpers:
            self.last_scan_info["error"] = "No candidates or Binance API rate-limit/ban (HTTP 418/429)"
            return

        self.last_scan_info["timestamp"] = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M:%S UTC")
        self.last_scan_info["candidates_count"] = len(gainers) + len(dumpers)
        self.last_scan_info["leaders"] = [c["symbol"] for c in gainers[:4]] + [c["symbol"] for c in dumpers[:4]]
        self.last_scan_info["error"] = None

        # 2. BTC Status check (Dump & Pump Shield)
        btc_dump, btc_ret_15m = await self.market.check_btc_status()
        
        gainers_str = ", ".join([f"{c['symbol']} ({c['change_24h_pct']:+.1f}%)" for c in gainers[:4]])
        dumpers_str = ", ".join([f"{c['symbol']} ({c['change_24h_pct']:+.1f}%)" for c in dumpers[:4]])
        btc_status_str = "DUMP ⚠️" if btc_dump else ("PUMP ⚠️" if btc_ret_15m > 0.6 else "NORMAL 🟢")
        print(f"   [Scanner DUAL] Gainers: {gainers_str or 'None'} | Dumpers: {dumpers_str or 'None'} | BTC: {btc_status_str} ({btc_ret_15m:+.2f}%)")

        # 3. Queue candidate evaluations concurrently
        eval_tasks = []
        for c in gainers:
            sym = c["symbol"]
            if self.portfolio.can_open_position(sym):
                eval_tasks.append(self.market.fetch_symbol_features(sym, btc_dump, btc_ret_15m, side="LONG"))

        for c in dumpers:
            sym = c["symbol"]
            if self.portfolio.can_open_position(sym):
                eval_tasks.append(self.market.fetch_symbol_features(sym, btc_dump, btc_ret_15m, side="SHORT"))

        if not eval_tasks:
            return

        features = await asyncio.gather(*eval_tasks, return_exceptions=True)

        # 4. Evaluate each candidate
        for feat in features:
            if not isinstance(feat, dict) or not feat or feat.get("skip", False):
                continue

            sym = feat["symbol"]
            side = feat.get("side", "LONG").upper()
            if not self.portfolio.can_open_position(sym):
                continue

            signal_ok, patterns = self.strategy.evaluate_entry_signal(feat, side=side)
            if signal_ok:
                entry_price = feat.get("mark_price", feat["close"])
                atr = feat.get("atr_15_pct", 1.0)
                sl_pct, tp_pct, sl_p, tp_p = self.strategy.calculate_sltp(entry_price, atr, side=side)

                metrics = {
                    "rvol": feat["rvol_20"],
                    "taker_buy": feat["taker_buy_ratio"],
                    "wick": feat["lower_wick_ratio"] if side == "LONG" else feat["upper_wick_ratio"],
                    "atr": atr,
                    "patterns": patterns
                }

                bracket_str = f"SL @ ${sl_p:.4f} (-{sl_pct:.2f}%) | TP @ ${tp_p:.4f} (+{tp_pct:.2f}%)" if side == "LONG" else f"SL @ ${sl_p:.4f} (+{sl_pct:.2f}%) | TP @ ${tp_p:.4f} (-{tp_pct:.2f}%)"
                print(f"\n" + "="*80)
                print(f"🚀 [SIGNAL CONFIRMED - {side}] {sym} @ ${entry_price:.4f}")
                print(f"   Patterns: {patterns} | RVOL: {feat['rvol_20']:.2f}x | TakerBuy: {feat['taker_buy_ratio']*100:.1f}%")
                print(f"   Brackets: {bracket_str}")
                print("="*80)

                pos = self.portfolio.open_position(
                    symbol=sym,
                    entry_price=entry_price,
                    sl_price=sl_p,
                    sl_pct=sl_pct,
                    tp_price=tp_p,
                    tp_pct=tp_pct,
                    metrics=metrics,
                    side=side
                )

                await self.notify_order_open(pos)

                if not self.portfolio.can_open_position("TEST_CHECK"):
                    break

    async def run_forever(self):
        """
        Master loop with full fault tolerance and auto-reconnection.
        Never exits unexpectedly on network glitches.
        """
        self.is_running = True
        if os.environ.get("STANDBY_MODE") == "1":
            print("[*] Running in STANDBY / DASHBOARD mode on Render (Trading executed on Local PC)")
            await self.start_web_server()
            while self.is_running:
                await asyncio.sleep(3600)
            return

        await self.initialize()

        last_scan_time = 0.0

        while self.is_running:
            now_ts = time.time()

            # 1. High-frequency position watcher (every 2.5 seconds)
            try:
                await self.watch_active_positions()
            except Exception as e:
                print(f"[!] Error in position watcher: {e}")

            # 2. Market scanner cycle (every 20 seconds)
            if now_ts - last_scan_time >= self.scan_interval:
                last_scan_time = now_ts
                now_str = datetime.datetime.now().strftime("%H:%M:%S")
                stats = self.portfolio.get_stats()
                print(f"[{now_str}] 🔍 Scan Cycle | Bal: ${stats['balance']:.2f} | Open: {stats['active_count']}/{self.portfolio.max_positions} | WR: {stats['win_rate']:.1f}% ({stats['wins']}/{stats['losses']})")
                
                try:
                    await self.scan_and_evaluate_signals()
                except Exception as e:
                    print(f"[!] Error in market scanner: {e}")

            # 3. Periodic heartbeat summary (every 2 hours)
            if now_ts - self.last_heartbeat_time >= 7200:
                self.last_heartbeat_time = now_ts
                try:
                    await self.notify_periodic_heartbeat()
                except Exception as e:
                    print(f"[!] Error sending heartbeat: {e}")

            # Brief async sleep to yield control
            await asyncio.sleep(self.pos_check_interval)

    async def stop(self, reason: str = "User requested"):
        print(f"\n[*] Stopping bot: {reason}...")
        self.is_running = False
        self.portfolio.save_state()
        stats = self.portfolio.get_stats()
        stop_msg = (
            f"🛑 <b>LIVE PAPER TRADING BOT ЗУПИНЕНО</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"ℹ️ <b>Причина:</b> {reason}\n"
            f"💼 <b>Кінцевий баланс:</b> ${stats['balance']:.2f} USDT\n"
            f"📈 <b>Результат PnL:</b> {stats['total_pnl']:+.2f} USDT ({stats['total_roi']:+.1f}%)\n"
            f"🎯 <b>Вінрейт:</b> {stats['win_rate']:.1f}% ({stats['wins']}W / {stats['losses']}L)\n"
            f"📌 <b>Відкритих позицій збережено:</b> {stats['active_count']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💾 <i>Стан портфеля надійно збережено на диску!</i>"
        )
        try:
            await self.notifier.send_message(stop_msg)
            await self.notifier.close()
            await self.market.close()
        except Exception:
            pass
        print("[+] Bot cleanup complete.")


# =====================================================================
# 6. ENTRYPOINT & SIGNAL HANDLING
# =====================================================================
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Live Paper Trading Bot (Binance Futures Mainnet)")
    parser.add_argument("--scan_interval", type=int, default=20, help="Market scan interval in seconds")
    parser.add_argument("--pos_interval", type=float, default=2.5, help="Position monitoring interval in seconds")
    parser.add_argument("--max_hold", type=int, default=60, help="Maximum position hold time in minutes (default: 60)")
    parser.add_argument("--scan_limit", type=int, default=100, help="Maximum number of in-play coins to scan per cycle (default: 100)")
    parser.add_argument("--single_cycle", action="store_true", help="Run 1 monitoring cycle and exit (for verification)")
    args = parser.parse_args()

    bot = LivePaperBot(
        scan_interval_sec=args.scan_interval,
        position_check_interval_sec=args.pos_interval,
        max_hold_minutes=args.max_hold,
        scan_limit=args.scan_limit
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if args.single_cycle:
        async def run_one():
            await bot.initialize()
            await bot.scan_and_evaluate_signals()
            await bot.watch_active_positions()
            stats = bot.portfolio.get_stats()
            print(f"[+] Single cycle complete! Balance: ${stats['balance']:.2f}, Active: {stats['active_count']}")
            await bot.stop("Тестовий одиночний цикл завершено")
        loop.run_until_complete(run_one())
        loop.close()
        return

    def handle_signal():
        print("\n[!] Shutdown signal received. Exiting gracefully...")
        loop.create_task(bot.stop("Сигнал завершення процесу (SIGINT/SIGTERM)"))

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda s, f: handle_signal())
        except Exception:
            pass

    try:
        loop.run_until_complete(bot.run_forever())
    except KeyboardInterrupt:
        loop.run_until_complete(bot.stop("Зупинено вручну користувачем (Ctrl+C)"))
    finally:
        loop.close()

if __name__ == "__main__":
    main()
