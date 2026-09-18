import polars as pl
import numpy as np
from numba import njit
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
from config import PROCESSED_DIR

@njit
def compute_smc_for_symbol(opens, highs, lows, closes, volumes, rvols, atr_pcts, 
                           min_fvg_pct=0.20, ob_lookback=12, max_active_bars=35):
    n = len(closes)
    
    fvg_bull_triggers = np.zeros(n, dtype=np.int32)
    ob_bull_triggers = np.zeros(n, dtype=np.int32)
    sr_flip_triggers = np.zeros(n, dtype=np.int32)
    confluence_score = np.zeros(n, dtype=np.int32)

    MAX_STRUCTS = 120  # FIX П4: Збільшено з 60 → 120, щоб не втрачати FVG/OB на волатильних монетах
    
    # 1. Bullish FVGs (Imbalances)
    fvg_count = 0
    fvg_idx = np.zeros(MAX_STRUCTS, dtype=np.int32)
    fvg_top = np.zeros(MAX_STRUCTS, dtype=np.float64)
    fvg_bot = np.zeros(MAX_STRUCTS, dtype=np.float64)

    # 2. Bullish Order Blocks (OB)
    ob_count = 0
    ob_idx = np.zeros(MAX_STRUCTS, dtype=np.int32)
    ob_top = np.zeros(MAX_STRUCTS, dtype=np.float64)
    ob_bot = np.zeros(MAX_STRUCTS, dtype=np.float64)

    # 3. S/R Flip Levels (Broken resistance turning into support)
    sr_count = 0
    sr_idx = np.zeros(MAX_STRUCTS, dtype=np.int32)
    sr_level = np.zeros(MAX_STRUCTS, dtype=np.float64)
    sr_broken = np.zeros(MAX_STRUCTS, dtype=np.int32) # 0=candidate resistance, 1=broken (now support)

    for i in range(2, n):
        curr_o = opens[i]
        curr_h = highs[i]
        curr_l = lows[i]
        curr_c = closes[i]

        # ----------------------------------------------------
        # A. DISCOVER NEW STRUCTURES
        # ----------------------------------------------------
        # 1. New Bullish FVG
        prev_h2 = highs[i-2]
        if curr_l > prev_h2:
            gap_pct = (curr_l - prev_h2) / prev_h2 * 100.0
            if gap_pct >= min_fvg_pct:
                if fvg_count < MAX_STRUCTS:
                    fvg_idx[fvg_count] = i
                    fvg_top[fvg_count] = curr_l
                    fvg_bot[fvg_count] = prev_h2
                    fvg_count += 1

        # 2. New Order Block (OB)
        if i >= ob_lookback + 2:
            recent_high = 0.0
            for k in range(i - ob_lookback - 1, i - 1):
                if highs[k] > recent_high:
                    recent_high = highs[k]
            
            # Displacement candle (BOS): close > recent swing high + high RVOL
            if curr_c > recent_high and rvols[i] >= 1.15 and (curr_c - curr_o) / curr_o * 100.0 >= 0.40:
                # Find the last bearish candle preceding this displacement
                ob_found_idx = -1
                for k in range(i - 1, max(0, i - 6), -1):
                    if closes[k] < opens[k]:
                        ob_found_idx = k
                        break
                if ob_found_idx != -1:
                    if ob_count < MAX_STRUCTS:
                        ob_idx[ob_count] = i
                        ob_top[ob_count] = max(opens[ob_found_idx], highs[ob_found_idx])
                        ob_bot[ob_count] = lows[ob_found_idx]
                        ob_count += 1

        # 3. New Resistance candidate (local swing high over 15 bars)
        if i >= 15:
            # Check if bar i-3 was a swing high
            sh_idx = i - 3
            is_sh = True
            for k in range(sh_idx - 5, sh_idx + 4):
                if k != sh_idx and highs[k] >= highs[sh_idx]:
                    is_sh = False
                    break
            if is_sh:
                if sr_count < MAX_STRUCTS:
                    sr_idx[sr_count] = sh_idx
                    sr_level[sr_count] = highs[sh_idx]
                    sr_broken[sr_count] = 0
                    sr_count += 1

        # ----------------------------------------------------
        # B. UPDATE S/R BREAKOUTS (Resistance -> Support Flip)
        # ----------------------------------------------------
        for k in range(sr_count):
            if sr_broken[k] == 0:
                lvl = sr_level[k]
                # Breakout occurred
                if curr_c > lvl and (curr_c - lvl) / lvl * 100.0 >= 0.20:
                    sr_broken[k] = 1 # Now it's a flipped support level!

        # ----------------------------------------------------
        # C. CHECK MITIGATION / REACTIONS ON CURRENT BAR i
        # ----------------------------------------------------
        candle_height = curr_h - curr_l + 1e-8
        lower_wick_ratio = (min(curr_o, curr_c) - curr_l) / candle_height
        is_bullish_reaction = (curr_c > curr_o) or (lower_wick_ratio >= 0.15)

        hit_fvg = False
        hit_ob = False
        hit_sr = False

        # 1. FVG Mitigation Check
        new_fvg_c = 0
        for k in range(fvg_count):
            age = i - fvg_idx[k]
            top = fvg_top[k]
            bot = fvg_bot[k]

            if age > max_active_bars:
                continue
            
            if curr_l <= top and curr_c >= bot:
                if is_bullish_reaction:
                    fvg_bull_triggers[i] = 1
                    hit_fvg = True
                continue # mitigated
            elif curr_c < bot:
                continue # invalidated
            else:
                fvg_idx[new_fvg_c] = fvg_idx[k]
                fvg_top[new_fvg_c] = top
                fvg_bot[new_fvg_c] = bot
                new_fvg_c += 1
        fvg_count = new_fvg_c

        # 2. OB Retest Check
        new_ob_c = 0
        for k in range(ob_count):
            age = i - ob_idx[k]
            top = ob_top[k]
            bot = ob_bot[k]

            if age > max_active_bars:
                continue
            
            # Dip into OB zone
            if curr_l <= top and curr_c >= bot * 0.998:
                if is_bullish_reaction:
                    ob_bull_triggers[i] = 1
                    hit_ob = True
                continue # mitigated
            elif curr_c < bot * 0.995:
                continue # invalidated
            else:
                ob_idx[new_ob_c] = ob_idx[k]
                ob_top[new_ob_c] = top
                ob_bot[new_ob_c] = bot
                new_ob_c += 1
        ob_count = new_ob_c

        # 3. S/R Flip Retest Check
        new_sr_c = 0
        for k in range(sr_count):
            age = i - sr_idx[k]
            lvl = sr_level[k]
            broken = sr_broken[k]

            if age > max_active_bars + 20:
                continue
            
            if broken == 1:
                # Retesting broken level as support: low dips near level (+-0.5%), close holds above
                # FIX П6: Розширено з 0.25% → 0.50% — крипто ліквідність часто збивають
                # до 0.3-0.5% нижче від рівня перед відскоком (liquidity sweep + recovery)
                dist_pct = (curr_l - lvl) / lvl * 100.0
                if dist_pct <= 0.50 and curr_c >= lvl * 0.997:
                    if is_bullish_reaction:
                        sr_flip_triggers[i] = 1
                        hit_sr = True
                    continue # retested
                elif curr_c < lvl * 0.992:
                    continue # broken back below (failed flip)
                else:
                    sr_idx[new_sr_c] = sr_idx[k]
                    sr_level[new_sr_c] = lvl
                    sr_broken[new_sr_c] = broken
                    new_sr_c += 1
            else:
                # Still candidate resistance
                if curr_c < lvl:
                    sr_idx[new_sr_c] = sr_idx[k]
                    sr_level[new_sr_c] = lvl
                    sr_broken[new_sr_c] = broken
                    new_sr_c += 1
        sr_count = new_sr_c

        # Confluence Score: how many SMC factors agree
        score = 0
        if hit_fvg:
            score += 1
        if hit_ob:
            score += 1
        if hit_sr:
            score += 1
        confluence_score[i] = score

    return fvg_bull_triggers, ob_bull_triggers, sr_flip_triggers, confluence_score

def compute_smc_matrix_all():
    print("[*] Loading Master Quant Matrix...")
    df = pl.read_parquet(PROCESSED_DIR / "inplay_master_quant_matrix.parquet")
    print(f"Total rows: {len(df):,}")

    symbols = df["symbol"].unique().to_list()
    print(f"Symbols to process: {len(symbols)}")

    t0 = time.time()
    
    # Process symbol by symbol
    res_chunks = []
    
    for sym in symbols:
        sub = df.filter(pl.col("symbol") == sym).sort("open_time")
        opens = sub["open"].to_numpy().astype(np.float64)
        highs = sub["high"].to_numpy().astype(np.float64)
        lows = sub["low"].to_numpy().astype(np.float64)
        closes = sub["close"].to_numpy().astype(np.float64)
        vols = sub["volume"].to_numpy().astype(np.float64)
        rvols = sub["rvol_20"].to_numpy().astype(np.float64)
        atrs = sub["atr_15_pct"].to_numpy().astype(np.float64)

        fvg, ob, sr, conf = compute_smc_for_symbol(opens, highs, lows, closes, vols, rvols, atrs)

        sub_smc = sub.select(["symbol", "open_time"]).with_columns([
            pl.Series("smc_fvg_bull", fvg),
            pl.Series("smc_ob_bull", ob),
            pl.Series("smc_sr_flip", sr),
            pl.Series("smc_confluence_score", conf)
        ])
        res_chunks.append(sub_smc)

    all_smc = pl.concat(res_chunks)
    print(f"[+] Computed SMC features in {time.time() - t0:.2f}s!")
    print(f"  Total FVG Bull Mitigations: {all_smc['smc_fvg_bull'].sum():,}")
    print(f"  Total OB Bull Retests:      {all_smc['smc_ob_bull'].sum():,}")
    print(f"  Total S/R Flip Retests:     {all_smc['smc_sr_flip'].sum():,}")
    print(f"  Total Confluence (Score>=2): {(all_smc['smc_confluence_score'] >= 2).sum():,}")

    print("[*] Merging back with Master Quant Matrix...")
    enhanced_df = df.join(all_smc, on=["symbol", "open_time"], how="left")
    out_path = PROCESSED_DIR / "inplay_master_smc_matrix.parquet"
    enhanced_df.write_parquet(out_path)
    print(f"[+] Successfully saved enhanced SMC matrix to: {out_path} ({len(enhanced_df):,} rows)")

if __name__ == "__main__":
    compute_smc_matrix_all()
