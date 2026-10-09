"""Airfare quote observations, NOT exchange-traded OHLC market data."""
from __future__ import annotations
import pandas as pd


def observed_series(quotes, departure, returning, source=None, mode=None):
    """A daily minimum among comparable quotes, for exactly one itinerary/provider/mode."""
    selected = [r for r in quotes if r.get('departure_date') == departure
                and r.get('return_date') == returning
                and (source is None or r.get('source') == source)
                and (mode is None or r.get('mode') == mode)
                and r.get('mode') not in ('TEST','LEGACY_UNDATED')]
    if not selected:
        return pd.DataFrame(columns=['date','price','open','high','low','close','observations'])
    df = pd.DataFrame(selected)
    df['observed_at'] = pd.to_datetime(df['observed_at'], utc=True, errors='coerce')
    df['price_twd'] = pd.to_numeric(df['price_twd'], errors='coerce')
    df = df.dropna(subset=['observed_at', 'price_twd'])
    df = df[df['price_twd'] > 0].sort_values('observed_at')
    if df.empty:
        return pd.DataFrame(columns=['date','price','open','high','low','close','observations'])
    df['date'] = df['observed_at'].dt.tz_convert('Asia/Taipei').dt.date
    # Same-date snapshot minimum is a quote; do not use all options as a market OHLC.
    points = df.groupby(['date','observed_at'],as_index=False)['price_twd'].min().sort_values('observed_at')
    daily = points.groupby('date')['price_twd'].agg(open='first',high='max',low='min',close='last',observations='size').reset_index()
    daily['price'] = daily['close']
    return daily


def technical_indicators(history):
    """EMA(12/26), MACD(9 signal), Wilder-style RSI(14). No synthetic forward fill."""
    df = history.copy()
    if df.empty:
        for c in ('ema12','ema26','macd','signal','histogram','rsi14'):
            df[c] = pd.Series(dtype='float64')
        return df
    c = df['close'].astype(float)
    # For very short series mark as unavailable rather than presenting false confidence.
    df['ema12'] = c.ewm(span=12, adjust=False, min_periods=12).mean()
    df['ema26'] = c.ewm(span=26, adjust=False, min_periods=26).mean()
    df['macd'] = df['ema12'] - df['ema26']
    df['signal'] = df['macd'].ewm(span=9,adjust=False,min_periods=9).mean()
    df['histogram'] = df['macd'] - df['signal']
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0,float('nan'))
    df['rsi14'] = (100-100/(1+rs)).mask((avg_loss==0)&(avg_gain>0),100).mask((avg_loss==0)&(avg_gain==0),50)
    return df


def price_stats(series):
    if series.empty:return {}
    close=series['close']
    current=float(close.iloc[-1]); low=float(close.min());median=float(close.median())
    return {'observations_days':len(series),'latest_twd':round(current), 'observed_low_twd':round(low),
            'observed_median_twd':round(median), 'vs_median_pct':round(100*(current/median-1),1),
            'vs_low_pct':round(100*(current/low-1),1),'last_seen':str(series['date'].iloc[-1])}
