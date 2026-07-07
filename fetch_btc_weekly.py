"""
fetch_btc_weekly.py
从 Binance 公开 API 拉取 BTC/USDT 周 K 线数据
每次运行自动追加新数据到已有文件（不覆盖历史数据）
支持从零开始也支持增量更新

用法: python3 fetch_btc_weekly.py
"""

import json
import os
from datetime import datetime, timezone
from urllib.request import urlopen


API_URL = "https://api.binance.com/api/v3/klines"
SYMBOL = "BTCUSDT"
INTERVAL = "1w"      # 周线
FETCH_LIMIT = 100    # 每次拉取量，足够覆盖缺漏

JSON_FILE = "btc_weekly_klines.json"
CSV_FILE = "btc_weekly_klines.csv"
CSV_HEADER = "date,open,high,low,close,volume"


def fmt_date(ts):
    return datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def fetch_raw_klines(start_time=None):
    """调用 Binance API，可选指定起始时间"""
    url = f"{API_URL}?symbol={SYMBOL}&interval={INTERVAL}&limit={FETCH_LIMIT}"
    if start_time:
        url += f"&startTime={start_time}"
    with urlopen(url) as resp:
        return json.loads(resp.read())


def raw_to_dict(k):
    return {
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


def load_existing_json(path):
    """加载已有 JSON 文件，返回 klines 列表；文件不存在则返回空列表"""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("data", [])


def merge_klines(old_list, new_list):
    """按 openTime 合并旧+新，最新的覆盖旧的（同一周取新值），按时间排序"""
    merged = {k["openTime"]: k for k in old_list}
    for k in new_list:
        merged[k["openTime"]] = k
    return sorted(merged.values(), key=lambda x: x["openTime"])


def to_csv_rows(klines):
    """kline dict 列表 → CSV 行列表（不含 header）"""
    return [
        f"{fmt_date(k['openTime'])},{k['open']},{k['high']},{k['low']},{k['close']},{k['volume']}"
        for k in klines
    ]


def save_json(path, klines):
    output = {
        "symbol": SYMBOL,
        "interval": INTERVAL,
        "count": len(klines),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "data": klines,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"✅ JSON → {path}  (累计 {len(klines)} 根)")


def save_csv(path, klines):
    rows = to_csv_rows(klines)
    content = CSV_HEADER + "\n" + "\n".join(rows)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"✅ CSV  → {path}  (累计 {len(klines)} 根)")


def main():
    try:
        # 1. 加载已有数据
        old_klines = load_existing_json(JSON_FILE)

        # 2. 决定拉取范围：增量 or 全量
        if old_klines:
            last_time = old_klines[-1]["openTime"]
            print(f"📂 已有 {len(old_klines)} 根，最新周: {fmt_date(last_time)}，增量拉取...")
            raw = fetch_raw_klines(start_time=last_time + 1)
            # Binance 可能返回已收盘的旧数据，但 startTime+1 保证了大部分是新数据
            # 为了稳妥，再补拉最近 FETCH_LIMIT 根兜底（覆盖未完结周线的更新）
            raw_latest = fetch_raw_klines()
            raw_dict = {k[0]: k for k in raw_latest}
            raw_dict.update({k[0]: k for k in raw})  # 后者覆盖前者
            all_new = sorted(raw_dict.values(), key=lambda x: x[0])
        else:
            print("📂 无历史数据，全量拉取...")
            all_new = fetch_raw_klines()

        new_klines = [raw_to_dict(k) for k in all_new]

        # 3. 合并去重
        merged = merge_klines(old_klines, new_klines)

        # 4. 保存
        save_json(JSON_FILE, merged)
        save_csv(CSV_FILE, merged)

        added = len(merged) - len(old_klines)
        if added > 0:
            print(f"📈 新增 {added} 根 K 线")
        else:
            print(f"ℹ️  无新增数据（最新周数据已更新）")

    except Exception as e:
        print(f"❌ 拉取失败: {e}")
        exit(1)


if __name__ == "__main__":
    main()
