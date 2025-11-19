import ccxt
import pandas as pd
from datetime import datetime, timedelta
import time

exchange = ccxt.binance({
    'enableRateLimit': True,
})

symbol = "BTC/USDT"
timeframe = "15m"
limit = 1000

# Fetch ~2 years
two_years_ms = 1000 * 60 * 60 * 24 * 365 * 2
now = exchange.milliseconds()
since = now - two_years_ms

all_ohlcv = []

print("Downloading BTC/USDT 15m candles... this may take 1–2 minutes.")

while True:
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit)
    except Exception as e:
        print("Error:", e)
        time.sleep(2)
        continue

    if not ohlcv:
        break

    all_ohlcv.extend(ohlcv)

    last_ts = ohlcv[-1][0]
    if last_ts <= since:
        break

    since = last_ts + (15 * 60 * 1000)
    if len(all_ohlcv) > 300_000:
        break

    time.sleep(exchange.rateLimit / 1000)

# Convert to DF
df = pd.DataFrame(all_ohlcv, columns=["timestamp","open","high","low","close","volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp")

out_path = "data/btc_usdt_15m.csv"
df.to_csv(out_path, index=False)

print(f"Saved: {out_path}")
print(f"Total candles: {len(df)}")
