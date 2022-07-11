import pandas as pd
from pandas.api.types import is_datetime64_any_dtype

def get_drift(x: int) -> int:
    """Returns an int if not zero, otherwise defaults to one."""
    return int(x) if isinstance(x, int) and x != 0 else 1

def panda_get_offset(x: int) -> int:
    """Returns an int, otherwise defaults to zero."""
    return int(x) if isinstance(x, int) else 0
def panda_verify_series(series: pd.Series, min_length: int = None) -> pd.Series:
    """If a Pandas Series and it meets the min_length of the indicator return it."""
    has_length = min_length is not None and isinstance(min_length, int)
    if series is not None and isinstance(series, pd.Series):
        return None if has_length and series.size < min_length else series
def panda_is_datetime_ordered(df: pd.DataFrame or pd.Series) -> bool:
    """Returns True if the index is a datetime and ordered."""
    index_is_datetime = is_datetime64_any_dtype(df.index)
    try:
        ordered = df.index[0] < df.index[-1]
    except RuntimeWarning:
        pass
    finally:
        return True if index_is_datetime and ordered else False

# ATR
def get_atr(high, low, period=None, length=None):
    """Indicator: ATR"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 7
    high = panda_verify_series(high, length)
    low = panda_verify_series(low, length)
    period = int(period) if period and period > 0 else 14

    if high is None or low is None: return

    # Calculate Results
    range_ = high - low
    atr_ = range_.rolling(period).mean()
    atr_return = pd.DataFrame({
        "high": high,
        "low": low,
        "atr": atr_
    }, index=high.index)
    
    return atr_return

# ADX
def get_adx(high, low, atr, period=None, length=None):
    """Indicator: ADX"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 7
    high = panda_verify_series(high, length)
    low = panda_verify_series(low, length)
    atr = panda_verify_series(atr, length)
    period = int(period) if period and period > 0 else 14

    if high is None or low is None or atr is None: return

    # Calculate Results
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    
    plus_di = 100 * (plus_dm.ewm(alpha = 1/period).mean() / atr)
    minus_di = abs(100 * (minus_dm.ewm(alpha = 1/period).mean() / atr))
    dx = (abs(plus_di - minus_di) / abs(plus_di + minus_di)) * 100
    adx = ((dx.shift(1) * (period - 1)) + dx) / period
    adx_smooth = adx.ewm(alpha = 1/period).mean()

    adx_return = pd.DataFrame({
        "high": high,
        "low": low,
        "pdm": plus_dm,
        "ndm": minus_dm,
        "pdi": plus_di,
        "ndi": minus_di,
        "adx": adx_smooth,
        "adx_smooth": adx_smooth
    }, index=high.index)

    return adx_return

# Supertrend
def get_supertrend(high, low, close, volume, atr_period=None, multiplier=None, length=None, offset=None):
    """Indicator: Supertrend"""
    # Validate Arguments
    atr_period = int(atr_period) if atr_period and atr_period > 0 else 14
    length = int(length) if length and length > 0 else 7
    multiplier = float(multiplier) if multiplier and multiplier > 0 else 3.0
    high = panda_verify_series(high, length)
    low = panda_verify_series(low, length)
    close = panda_verify_series(close, length)
    volume = panda_verify_series(volume, length)
    offset = panda_get_offset(offset)
    atr = get_atr(high, low, atr_period)['atr']

    if high is None or low is None or close is None: return

    # Calculate Results
    m = close.size
    dir_, trend = [1] * m, [0] * m
    long, short = [None] * m, [None] * m

    hl_avg = (high + low + close) / 3
    
    hl_avg = (hl_avg * volume) / volume.mean()
    closeB4 = close
    close = (close * volume) / volume.mean()
    #print("VoluemeMean:", volume.mean())
    
    matr = multiplier * atr
    upperband = hl_avg + matr
    lowerband = hl_avg - matr

    for i in range(1, m):
        if close.iloc[i] > upperband.iloc[i - 1]:
            dir_[i] = 1
        elif close.iloc[i] < lowerband.iloc[i - 1]:
            dir_[i] = -1
        else:
            dir_[i] = dir_[i - 1]
            if dir_[i] > 0 and lowerband.iloc[i] < lowerband.iloc[i - 1]:
                lowerband.iloc[i] = lowerband.iloc[i - 1]
            if dir_[i] < 0 and upperband.iloc[i] > upperband.iloc[i - 1]:
                upperband.iloc[i] = upperband.iloc[i - 1]

        if dir_[i] > 0:
            trend[i] = long[i] = lowerband.iloc[i]
        else:
            trend[i] = short[i] = upperband.iloc[i]

    # Prepare DataFrame to return
    supertrend_return = pd.DataFrame({
            "high": high,
            "low": low,
            "close": closeB4,
            "volume_weighted_close": close,
            "volume": volume,
            "supertrend": trend,
            "supertrend_direction": dir_,
            "supertrend_long": long,
            "supertrend_short": short,
        }, index=close.index)
    supertrend_return['supertrend_is_uptrend'] = supertrend_return['supertrend_direction'] == 1
        
    # Apply offset if needed
    if offset != 0:
        supertrend_return = supertrend_return.shift(offset)

    return supertrend_return

#VWAP
def get_vwap(high, low, close, volume, anchor=None, offset=None):
    """Indicator: Volume Weighted Average Price (VWAP)"""
    # Validate Arguments
    high = panda_verify_series(high)
    low = panda_verify_series(low)
    close = panda_verify_series(close)
    volume = panda_verify_series(volume)
    anchor = anchor.upper() if anchor and isinstance(anchor, str) and len(anchor) >= 1 else "D"
    offset = panda_get_offset(offset)

    typical_price = (high + low + close) / 3
    if not panda_is_datetime_ordered(volume):
        print(f"[!] VWAP volume series is not datetime ordered. Results may not be as expected.")
    if not panda_is_datetime_ordered(typical_price):
        print(f"[!] VWAP price series is not datetime ordered. Results may not be as expected.")

    # Calculate Result
    wp = typical_price * volume
    vwap  = wp.groupby(wp.index.to_period(anchor)).cumsum()
    vwap /= volume.groupby(volume.index.to_period(anchor)).cumsum()

    # Offset
    if offset != 0:
        vwap = vwap.shift(offset)
        
    return pd.DataFrame({
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "vwap": vwap
    }, index=close.index)

# RSI
def get_rsi(open_, close, period=None, length=None):
    """Indicator: RSI"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 7
    open_ = panda_verify_series(open_, length)
    close = panda_verify_series(close, length)
    period = int(period) if period and period > 0 else 14

    if open_ is None or close is None: return

    # Calculate Results
    rsi_return = pd.DataFrame({
        "open": open_,
        "close": close
    }, index=open_.index)
    # to calculate RSI, we first need to calculate the exponential weighted aveage gain and loss during the period
    rsi_return['gain'] = (close - open_).apply(lambda x: x if x > 0 else 0)
    rsi_return['loss'] = (close - open_).apply(lambda x: -x if x < 0 else 0)

    # here we use the same formula to calculate Exponential Moving Average
    rsi_return['ema_gain'] = rsi_return['gain'].ewm(span=period, min_periods=period).mean()
    rsi_return['ema_loss'] = rsi_return['loss'].ewm(span=period, min_periods=period).mean()

    # the Relative Strength is the ratio between the exponential avg gain divided by the exponential avg loss
    rsi_return['rs'] = rsi_return['ema_gain'] / rsi_return['ema_loss']

    # the RSI is calculated based on the Relative Strength using the folcloseing formula
    rsi_return['rsi'] = 100 - (100 / (rsi_return['rs'] + 1))
    #max_close = close.max()
    #rsi_return['rsi_14_close_scaled'] = max_close - (max_close / (rsi_return['rs'] + 1))

    return rsi_return

# MFI
def get_mfi(close, high, low, volume, period=None, length=None, drift=None):
    """Indicator: RSI"""
    # Validate Arguments
    length = int(length) if length and length > 0 else 7
    close = panda_verify_series(close, length)
    high = panda_verify_series(high, length)
    low = panda_verify_series(low, length)
    volume = panda_verify_series(volume, length)
    period = int(period) if period and period > 0 else 14
    drift = get_drift(drift)

    if close is None or high is None or low is None or volume is None: return

    # Calculate Results
    typical_price = (close + high + low) / 3
    raw_money_flow = typical_price * volume

    tdf = pd.DataFrame({"diff": 0, "rmf": raw_money_flow, "+mf": 0, "-mf": 0})

    tdf.loc[(typical_price.diff(drift) > 0), "diff"] = 1
    tdf.loc[tdf["diff"] == 1, "+mf"] = raw_money_flow

    tdf.loc[(typical_price.diff(drift) < 0), "diff"] = -1
    tdf.loc[tdf["diff"] == -1, "-mf"] = raw_money_flow

    psum = tdf["+mf"].rolling(length).sum()
    nsum = tdf["-mf"].rolling(length).sum()
    tdf["mr"] = psum / nsum
    mfi = 100 * psum / (psum + nsum)
    tdf["mfi"] = mfi

    mfi_return = pd.DataFrame({
        "close": close,
        "high": high,
        "low": low,
        "volume": volume,
        "pmf": tdf["+mf"],
        "nmf": tdf["-mf"],
        "mfi": mfi
    }, index=close.index)

    return mfi_return

