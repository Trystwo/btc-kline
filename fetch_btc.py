"""
fetch_btc.py
从 Binance 公开 API 拉取 BTC/USDT K 线数据
每次运行自动追加新数据到已有文件（不覆盖历史数据）
支持多级别: 1w (周), 1d (日), 4h (4小时), 1h (1小时)

用法: python3 fetch_btc.py <interval>
示例:
  python3 fetch_btc.py 1w    # 周线
  python3 fetch_btc.py 1d    # 日线
  python3 fetch_btc.py 4h    # 4小时
  python3 fetch_btc.py 1h    # 1小时
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import urlopen


API_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"

# 级别配置: {interval: (首次拉取量, 时间跨度标签)}
INTERVAL_CONFIG = {
    "1w": (30,   "周"),
    "1d": (90,   "日"),
    "4h": (42,   "4小时"),
    "1h": (72,   "1小时"),
}

DATA_DIR = "data"


def fmt_datetime(ts, interval):
    """时间戳格式化，周/日用日期，4H/1H精确到分钟"""
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    if interval in ("1w", "1d"):
        return dt.strftime("%Y-%m-%d")
    else:
        return dt.strftime("%Y-%m-%d %H:%M")


def fetch_raw_klines(interval, limit, start_time=None):
    """调用 Binance API，可选指定起始时间"""
    url = f"{API_URL}?symbol={SYMBOL}&interval={interval}&limit={limit}"
    if start_time:
        url += f"&startTime={start_time}"
    with urlopen(url) as resp:
        return json.loads(resp.read())


def raw_to_dict(k, interval):
    return {
        "openTime": k[0],
        "openTimeStr": fmt_datetime(k[0], interval),
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


def load_existing_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("data", [])


def merge_klines(old_list, new_list):
    """按 openTime 合并旧+新，最新的覆盖旧的，按时间排序"""
    merged = {k["openTime"]: k for k in old_list}
    for k in new_list:
        merged[k["openTime"]] = k
    return sorted(merged.values(), key=lambda x: x["openTime"])


def to_csv_rows(klines, interval):
    return [
        f"{k['openTimeStr']},{k['open']},{k['high']},{k['low']},{k['close']},{k['volume']}"
        for k in klines
    ]


def save_json(path, klines, interval):
    label = INTERVAL_CONFIG[interval][1]
    output = {
        "symbol": SYMBOL,
        "interval": interval,
        "count": len(klines),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "data": klines,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON → {path}  (累计 {len(klines)} 根{label}K)")


def save_csv(path, klines, interval):
    header = "date,open,high,low,close,volume"
    rows = to_csv_rows(klines, interval)
    content = header + "\n" + "\n".join(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    label = INTERVAL_CONFIG[interval][1]
    print(f"✅ CSV  → {path}  (累计 {len(klines)} 根{label}K)")


def main():
    if len(sys.argv) < 2:
        print("用法: python3 fetch_btc.py <interval>")
        print(f"支持级别: {', '.join(INTERVAL_CONFIG.keys())}")
        print("示例: python3 fetch_btc.py 1d")
        sys.exit(1)

    interval = sys.argv[1]
    if interval not in INTERVAL_CONFIG:
        print(f"❌ 不支持的级别: {interval}，可选: {', '.join(INTERVAL_CONFIG.keys())}")
        sys.exit(1)

    init_limit, label = INTERVAL_CONFIG[interval]
    base_name = f"btc_klines_{interval}"
    json_path = os.path.join(DATA_DIR, f"{base_name}.json")
    csv_path = os.path.join(DATA_DIR, f"{base_name}.csv")

    try:
        # 1. 加载已有数据
        old_klines = load_existing_json(json_path)

        # 2. 拉取新数据
        if old_klines:
            last_time = old_klines[-1]["openTime"]
            print(f"📂 已有 {len(old_klines)} 根{label}K，最新: {fmt_datetime(last_time, interval)}，增量拉取...")

            # 增量：从最新之后开始
            raw_inc = fetch_raw_klines(interval, init_limit, start_time=last_time + 1)
            # 兜底：拉最新 init_limit 根，覆盖未完结 K 线的更新
            raw_latest = fetch_raw_klines(interval, init_limit)
            # 合并（后者覆盖前者）
            raw_dict = {k[0]: k for k in raw_latest}
            raw_dict.update({k[0]: k for k in raw_inc})
            all_new = sorted(raw_dict.values(), key=lambda x: x[0])
        else:
            print(f"📂 无历史数据，拉取最近 {init_limit} 根{label}K...")
            all_new = fetch_raw_klines(interval, init_limit)

        new_klines = [raw_to_dict(k, interval) for k in all_new]

        # 3. 合并去重
        merged = merge_klines(old_klines, new_klines)

        # 4. 保存
        save_json(json_path, merged, interval)
        save_csv(csv_path, merged, interval)

        added = len(merged) - len(old_klines)
        if added > 0:
            print(f"📈 新增 {added} 根{label}K")
        else:
            print(f"ℹ️  无新增数据（最新{label}K数据已更新）")

    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
