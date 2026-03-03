"""
Technical indicator computation library.

All functions:
- Accept numpy arrays (float64)
- Return numpy arrays of the same length (NaN-padded during warmup)
- Are stateless and parallelisable
- Validated against pandas-ta reference outputs
"""
import numpy as np


# ─── Trend ────────────────────────────────────────────────────────────────────

def compute_sma(close: np.ndarray, period: int) -> np.ndarray:
    """Simple Moving Average."""
    result = np.full(len(close), np.nan)
    for i in range(period - 1, len(close)):
        result[i] = np.mean(close[i - period + 1:i + 1])
    return result


def compute_ema(close: np.ndarray, period: int) -> np.ndarray:
    """Exponential Moving Average."""
    result = np.full(len(close), np.nan)
    k = 2.0 / (period + 1)
    # seed with SMA of first `period` values
    result[period - 1] = np.mean(close[:period])
    for i in range(period, len(close)):
        result[i] = close[i] * k + result[i - 1] * (1 - k)
    return result


def compute_macd(
    close: np.ndarray,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """MACD line, signal line, histogram."""
    ema_fast = compute_ema(close, fast)
    ema_slow = compute_ema(close, slow)
    macd_line = ema_fast - ema_slow
    # Signal is EMA of MACD; only compute from first non-NaN MACD value
    first_valid = slow - 1
    signal_line = np.full(len(close), np.nan)
    if len(close) > first_valid + signal:
        macd_valid = macd_line[first_valid:]
        signal_valid = compute_ema(macd_valid, signal)
        signal_line[first_valid:] = signal_valid
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


# ─── Momentum ─────────────────────────────────────────────────────────────────

def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index using Wilder's smoothing."""
    result = np.full(len(close), np.nan)
    if len(close) < period + 1:
        return result
    deltas = np.diff(close)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    # Seed with simple average
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])
    for i in range(period, len(close)):
        idx = i - period  # index into deltas/gains/losses
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - (100.0 / (1.0 + rs))
    return result


def compute_roc(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Rate of Change: ((close - close[n]) / close[n]) * 100."""
    result = np.full(len(close), np.nan)
    for i in range(period, len(close)):
        prev = close[i - period]
        if prev != 0:
            result[i] = ((close[i] - prev) / prev) * 100
    return result


def compute_stochastic(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    k_period: int = 14,
    d_period: int = 3,
) -> tuple[np.ndarray, np.ndarray]:
    """Stochastic %K and %D."""
    k = np.full(len(close), np.nan)
    for i in range(k_period - 1, len(close)):
        h = np.max(high[i - k_period + 1:i + 1])
        l = np.min(low[i - k_period + 1:i + 1])
        if h != l:
            k[i] = ((close[i] - l) / (h - l)) * 100
        else:
            k[i] = 50.0
    d = compute_sma(k, d_period)
    return k, d


# ─── Volatility ───────────────────────────────────────────────────────────────

def compute_bollinger_bands(
    close: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Upper band, middle band (SMA), lower band."""
    middle = compute_sma(close, period)
    upper = np.full(len(close), np.nan)
    lower = np.full(len(close), np.nan)
    for i in range(period - 1, len(close)):
        std = np.std(close[i - period + 1:i + 1], ddof=0)
        upper[i] = middle[i] + std_dev * std
        lower[i] = middle[i] - std_dev * std
    return upper, middle, lower


def compute_bb_width(
    close: np.ndarray, period: int = 20, std_dev: float = 2.0
) -> np.ndarray:
    """Bollinger Band width: (upper - lower) / middle. Used for squeeze detection."""
    upper, middle, lower = compute_bollinger_bands(close, period, std_dev)
    width = np.full(len(close), np.nan)
    valid = middle != 0
    width[valid] = (upper[valid] - lower[valid]) / middle[valid]
    return width


def compute_atr(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> np.ndarray:
    """Average True Range using Wilder's smoothing."""
    n = len(close)
    tr = np.full(n, np.nan)
    for i in range(1, n):
        hl = high[i] - low[i]
        hpc = abs(high[i] - close[i - 1])
        lpc = abs(low[i] - close[i - 1])
        tr[i] = max(hl, hpc, lpc)
    atr = np.full(n, np.nan)
    if n > period:
        atr[period] = np.mean(tr[1:period + 1])
        for i in range(period + 1, n):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return atr


def compute_adx(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    period: int = 14,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ADX, +DI, -DI using Wilder's smoothing."""
    n = len(close)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    tr_arr = np.zeros(n)

    for i in range(1, n):
        up_move = high[i] - high[i - 1]
        down_move = low[i - 1] - low[i]
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0
        tr_arr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))

    smoothed_plus_dm = np.full(n, np.nan)
    smoothed_minus_dm = np.full(n, np.nan)
    smoothed_tr = np.full(n, np.nan)

    if n <= period:
        return np.full(n, np.nan), np.full(n, np.nan), np.full(n, np.nan)

    smoothed_plus_dm[period] = np.sum(plus_dm[1:period + 1])
    smoothed_minus_dm[period] = np.sum(minus_dm[1:period + 1])
    smoothed_tr[period] = np.sum(tr_arr[1:period + 1])

    for i in range(period + 1, n):
        smoothed_plus_dm[i] = smoothed_plus_dm[i-1] - smoothed_plus_dm[i-1]/period + plus_dm[i]
        smoothed_minus_dm[i] = smoothed_minus_dm[i-1] - smoothed_minus_dm[i-1]/period + minus_dm[i]
        smoothed_tr[i] = smoothed_tr[i-1] - smoothed_tr[i-1]/period + tr_arr[i]

    plus_di = np.full(n, np.nan)
    minus_di = np.full(n, np.nan)
    dx = np.full(n, np.nan)

    for i in range(period, n):
        if smoothed_tr[i] != 0:
            plus_di[i] = 100 * smoothed_plus_dm[i] / smoothed_tr[i]
            minus_di[i] = 100 * smoothed_minus_dm[i] / smoothed_tr[i]
            di_sum = plus_di[i] + minus_di[i]
            if di_sum != 0:
                dx[i] = 100 * abs(plus_di[i] - minus_di[i]) / di_sum

    adx = np.full(n, np.nan)
    first_adx_idx = 2 * period - 1
    if n > first_adx_idx:
        adx[first_adx_idx] = np.nanmean(dx[period:first_adx_idx + 1])
        for i in range(first_adx_idx + 1, n):
            if not np.isnan(dx[i]):
                adx[i] = (adx[i-1] * (period - 1) + dx[i]) / period

    return adx, plus_di, minus_di


# ─── Volume ───────────────────────────────────────────────────────────────────

def compute_obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """On-Balance Volume."""
    obv = np.zeros(len(close))
    obv[0] = volume[0]
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            obv[i] = obv[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            obv[i] = obv[i - 1] - volume[i]
        else:
            obv[i] = obv[i - 1]
    return obv


def compute_vwap(
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    session_boundaries: list[int] | None = None,
) -> np.ndarray:
    """
    Volume-Weighted Average Price.

    Resets at each session boundary index. If session_boundaries is None,
    VWAP is computed continuously (useful for daily/weekly data).
    """
    n = len(close)
    vwap = np.full(n, np.nan)
    typical = (high + low + close) / 3.0

    if session_boundaries is None:
        cum_tp_vol = np.cumsum(typical * volume)
        cum_vol = np.cumsum(volume)
        valid = cum_vol > 0
        vwap[valid] = cum_tp_vol[valid] / cum_vol[valid]
        return vwap

    boundaries = sorted(set([0] + session_boundaries + [n]))
    for j in range(len(boundaries) - 1):
        start = boundaries[j]
        end = boundaries[j + 1]
        seg_tp = typical[start:end]
        seg_vol = volume[start:end]
        cum_tp_vol = np.cumsum(seg_tp * seg_vol)
        cum_vol = np.cumsum(seg_vol)
        valid = cum_vol > 0
        seg_vwap = np.full(end - start, np.nan)
        seg_vwap[valid] = cum_tp_vol[valid] / cum_vol[valid]
        vwap[start:end] = seg_vwap

    return vwap


# ─── Signal helpers ───────────────────────────────────────────────────────────

def crosses_above(series_a: np.ndarray, series_b: np.ndarray) -> np.ndarray:
    """
    Boolean array: True where series_a crosses above series_b.

    A crossover is detected when series_a was at or below series_b on the
    previous bar and is at or above series_b on the current bar, with at
    least one of those conditions being strict (i.e. the two series are not
    both exactly equal on both bars).
    """
    result = np.zeros(len(series_a), dtype=bool)
    for i in range(1, len(series_a)):
        was_below_or_equal = series_a[i - 1] <= series_b[i - 1]
        is_above_or_equal = series_a[i] >= series_b[i]
        not_flat = not (series_a[i - 1] == series_b[i - 1] and series_a[i] == series_b[i])
        result[i] = was_below_or_equal and is_above_or_equal and not_flat
    return result


def crosses_below(series_a: np.ndarray, series_b: np.ndarray) -> np.ndarray:
    """
    Boolean array: True where series_a crosses below series_b.

    A crossover is detected when series_a was at or above series_b on the
    previous bar and is at or below series_b on the current bar, with at
    least one of those conditions being strict (i.e. the two series are not
    both exactly equal on both bars).
    """
    result = np.zeros(len(series_a), dtype=bool)
    for i in range(1, len(series_a)):
        was_above_or_equal = series_a[i - 1] >= series_b[i - 1]
        is_below_or_equal = series_a[i] <= series_b[i]
        not_flat = not (series_a[i - 1] == series_b[i - 1] and series_a[i] == series_b[i])
        result[i] = was_above_or_equal and is_below_or_equal and not_flat
    return result
