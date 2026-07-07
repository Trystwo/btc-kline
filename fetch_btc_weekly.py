"""
fetch_btc_weekly.py
从 Binance 公开 API 拉取 BTC/USDT 周 K 线数据
同时保存为 JSON 和 CSV 文件（CSV 适合喂给 AI 分析）

用法: python3 fetch_btc_weekly.py
"""

import json
import csv
from datetime import datetime, timezone
from urllib.request import urlopen


API_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1w"   # 周线
LIMIT = 30


def fetch_klines():
    url = f"{API_URL}?symbol={SYMBOL}&interval={INTERVAL}&limit={LIMIT}"
    with urlopen(url) as resp:
        raw = json.loads(resp.read())

    return [
        {
            "openTime": k[0],
            "openTimeISO": datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).isoformat(),
            "open": k[1],
            "high": k[2],
            "low": k[3],
            "close": k[4],
            "volume": k[5],
            "closeTime": k[6],
            "closeTimeISO": datetime.fromtimestamp(k[6] / 1000, tz=timezone.utc).isoformat(),
            "quoteVolume": k[7],
            "trades": k[8],
            "takerBuyBaseVol": k[9],
            "takerBuyQuoteVol": k[10],
        }
        for k in raw
    ]


def to_csv(klines):
    """转 CSV 字符串（精简列，适合 AI 分析）"""
    header = "date,open,high,low,close,volume"
    rows = [
        f"{datetime.fromtimestamp(k['openTime'] / 1000, tz=timezone.utc).strftime('%Y-%m-%d')},"
        f"{k['open']},{k['high']},{k['low']},{k['close']},{k['volume']}"
        for k in klines
    ]
    return "\n".join([header] + rows)


def main():
    try:
        klines = fetch_klines()

        # JSON
        output = {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "count": len(klines),
            "fetchedAt": datetime.now(timezone.utc).isoformat(),
            "data": klines,
        }
        with open("btc_weekly_klines.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        print(f"✅ JSON → btc_weekly_klines.json  ({len(klines)} 根)")

        # CSV
        csv_str = to_csv(klines)
        with open("btc_weekly_klines.csv", "w", encoding="utf-8", newline="") as f:
            f.write(csv_str)
        print(f"✅ CSV  → btc_weekly_klines.csv   ({len(klines)} 根)")

    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        exit(1)


if __name__ == "__main__":
    main()
