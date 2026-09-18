import os
from pathlib import Path

BASE_DIR = Path(r'C:\Users\User\.gemini\antigravity\scratch\binance_inplay_analyzer')
DATA_DIR = BASE_DIR / 'data'
RAW_DIR = DATA_DIR / 'raw'
PROCESSED_DIR = DATA_DIR / 'processed'
REPORTS_DIR = BASE_DIR / 'reports'

for p in [DATA_DIR, RAW_DIR, PROCESSED_DIR, REPORTS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

FUTURES_API_URL = 'https://fapi.binance.com'
SPOT_API_URL = 'https://api.binance.com'

MIN_DAILY_RANGE_PCT = 0.50
MIN_DAILY_VOLUME_USDT = 10_000_000
IMPULSE_1M_THRESHOLD_PCT = 0.025
PRE_IMPULSE_WINDOW_MINUTES = 30
OUT_OF_SAMPLE_RATIO = 0.30
