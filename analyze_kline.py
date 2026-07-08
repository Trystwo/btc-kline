"""
analyze_kline.py
调用 DeepSeek API 分析 BTC K 线数据
支持多级别: 1w (周), 1d (日), 4h (4小时), 1h (1小时)
分析报告保存到 reports/，请求原文保存到 requests/

用法: python3 analyze_kline.py <interval>
示例:
  python3 analyze_kline.py 1w    # 分析周线
  python3 analyze_kline.py 1d    # 分析日线
  python3 analyze_kline.py 4h    # 分析4小时
  python3 analyze_kline.py 1h    # 分析1小时
"""

import json
import os
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"
DATA_DIR = "data"
PROMPTS_DIR = "prompts"
REPORTS_DIR = "reports"
REQUESTS_DIR = "requests"

INTERVAL_LABEL = {
    "1w": ("周",   "宏观趋势"),
    "1d": ("日",   "中期走势"),
    "4h": ("4小时", "短线交易"),
    "1h": ("1小时", "超短线"),
}


def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    if not lines:
        raise ValueError("CSV 文件为空")
    return lines[0], lines[1:]  # header, rows


def build_user_message(interval, header, rows):
    label = INTERVAL_LABEL[interval][0]
    data_str = "\n".join([header] + rows)
    return f"请对以下 BTC/USDT {label}K线数据（OHLCV）进行分析：\n\n```\n{data_str}\n```"


def call_deepseek(api_key, messages):
    payload = {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 2048,
    }
    req = Request(
        DEEPSEEK_API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read())
    return result["choices"][0]["message"]["content"]


def save_request(interval, messages):
    """保存完整 API 请求消息到 requests/"""
    os.makedirs(REQUESTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REQUESTS_DIR, f"{interval}_{ts}.json")
    record = {
        "interval": interval,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messages": messages,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)
    print(f"📝 请求原文 → {path}")
    return path


def save_report(interval, analysis):
    """保存分析报告到 reports/"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    label = INTERVAL_LABEL[interval][0]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"{interval}_{ts}.md")
    content = f"# BTC {label}K 线技术分析\n\n生成时间: {datetime.now()}\n\n{analysis}\n"
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"📄 分析报告 → {path}")
    return path


def main():
    if len(sys.argv) < 2:
        print("用法: python3 analyze_kline.py <interval>")
        print(f"支持级别: {', '.join(INTERVAL_LABEL.keys())}")
        print("示例: python3 analyze_kline.py 1d")
        sys.exit(1)

    interval = sys.argv[1]
    if interval not in INTERVAL_LABEL:
        print(f"❌ 不支持的级别: {interval}，可选: {', '.join(INTERVAL_LABEL.keys())}")
        sys.exit(1)

    label = INTERVAL_LABEL[interval][0]
    csv_path = os.path.join(DATA_DIR, f"btc_klines_{interval}.csv")
    prompt_path = os.path.join(PROMPTS_DIR, f"prompt_{interval}.md")

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    try:
        header, rows = read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ 找不到数据文件: {csv_path}，请先运行 python3 fetch_btc.py {interval}")
        sys.exit(1)

    try:
        system_prompt = load_prompt(prompt_path)
    except FileNotFoundError:
        print(f"❌ 找不到提示词文件: {prompt_path}")
        sys.exit(1)

    print(f"📊 读取 {len(rows)} 根{label}K 线，正在调用 DeepSeek 分析...\n")

    user_msg = build_user_message(interval, header, rows)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    # 保存请求原文
    save_request(interval, messages)

    try:
        analysis = call_deepseek(api_key, messages)
    except URLError as e:
        print(f"❌ API 调用失败: {e}")
        sys.exit(1)

    print("=" * 56)
    print(analysis)
    print("=" * 56)

    # 保存分析报告
    save_report(interval, analysis)
    print(f"\n✅ 分析完成")


if __name__ == "__main__":
    main()
