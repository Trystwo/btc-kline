"""
analyze_kline.py
调用 DeepSeek API 分析 BTC 周 K 线数据
用法: python3 analyze_kline.py [csv文件路径]
"""

import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import URLError

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"
DEFAULT_CSV = "btc_weekly_klines.csv"
PROMPT_FILE = "prompt_kline_analysis.md"

def load_prompt(path=PROMPT_FILE):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    if not lines:
        raise ValueError("CSV 文件为空")
    return lines[0], lines[1:]  # header, rows


def build_prompt(header, rows):
    data_str = "\n".join([header] + rows)
    return f"以下为 BTC/USDT 最近 {len(rows)} 根周 K 线数据（OHLCV）：\n\n```\n{data_str}\n```\n\n请对以上数据做技术分析。"


def call_deepseek(api_key, messages):
    payload = {
        "model": "deepseek-chat",
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


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CSV

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    try:
        header, rows = read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ 找不到文件: {csv_path} 或提示词文件 {PROMPT_FILE}，请先运行 fetch_btc_weekly.py")
        sys.exit(1)

    print(f"📊 读取 {len(rows)} 根周 K 线，正在调用 DeepSeek 分析...\n")

    messages = [
        {"role": "system", "content": load_prompt()},
        {"role": "user", "content": build_prompt(header, rows)},
    ]

    try:
        analysis = call_deepseek(api_key, messages)
    except URLError as e:
        print(f"❌ API 调用失败: {e}")
        sys.exit(1)

    print("=" * 56)
    print(analysis)
    print("=" * 56)

    # 同时保存到文件
    output_path = "btc_kline_analysis.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"# BTC 周 K 线技术分析\n\n生成时间: {__import__('datetime').datetime.now().__str__()}\n\n")
        f.write(analysis + "\n")
    print(f"\n✅ 分析报告已保存到 {output_path}")


if __name__ == "__main__":
    main()
