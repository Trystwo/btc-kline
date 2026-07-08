"""
suggest_positions.py
基于技术分析报告 + K 线数据，调用 DeepSeek 给出做多/做空交易信号
信号保存到 positions/

用法: python3 suggest_positions.py <interval>
示例:
  python3 suggest_positions.py 1d    # 基于日线分析出交易信号
  python3 suggest_positions.py 4h    # 基于4小时分析出交易信号
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.error import URLError

DEEPSEEK_API = "https://api.deepseek.com/chat/completions"
DATA_DIR = "data"
REPORTS_DIR = "reports"
POSITIONS_DIR = "positions"
PROMPTS_DIR = "prompts"

INTERVAL_LABEL = {
    "1w": "周",
    "1d": "日",
    "4h": "4小时",
    "1h": "1小时",
}


def load_prompt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().strip().splitlines()
    if not lines:
        raise ValueError("CSV 文件为空")
    return lines[0], lines[1:]


def find_latest_report(interval):
    """找到指定级别最新的分析报告"""
    pattern = re.compile(rf"^{re.escape(interval)}_\d{{8}}_\d{{6}}\.md$")
    candidates = []
    for f in os.listdir(REPORTS_DIR):
        if pattern.match(f):
            path = os.path.join(REPORTS_DIR, f)
            candidates.append((os.path.getmtime(path), path))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def build_user_message(interval, analysis, header, rows):
    label = INTERVAL_LABEL[interval]
    data_str = "\n".join([header] + rows[-10:])  # 只给最近 10 根 K 线确认当前位置
    return (
        f"## BTC {label}K 技术分析报告\n\n"
        f"{analysis}\n\n"
        f"## 最近 {label}K 线数据\n\n"
        f"```\n{data_str}\n```\n\n"
        f"请基于以上分析给出交易计划。"
    )


def call_deepseek(api_key, messages):
    payload = {
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": 0.1,  # 低温度让输出更稳定
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


def extract_json(text):
    """从 AI 回复中提取 JSON 块"""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # 如果没有代码块，尝试直接解析
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1:
        return json.loads(text[brace_start : brace_end + 1])
    raise ValueError("无法从回复中提取 JSON")


def save_position(interval, result):
    os.makedirs(POSITIONS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(POSITIONS_DIR, f"{interval}_{ts}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"📊 交易信号 → {path}")
    return path


def main():
    if len(sys.argv) < 2:
        print("用法: python3 suggest_positions.py <interval>")
        print(f"支持级别: {', '.join(INTERVAL_LABEL.keys())}")
        print("示例: python3 suggest_positions.py 1d")
        sys.exit(1)

    interval = sys.argv[1]
    if interval not in INTERVAL_LABEL:
        print(f"❌ 不支持的级别: {interval}")
        sys.exit(1)

    label = INTERVAL_LABEL[interval]
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    # 1. 读取最新分析报告
    report_path = find_latest_report(interval)
    if not report_path:
        print(f"❌ 找不到 {interval} 级别的分析报告，请先运行 python3 analyze_kline.py {interval}")
        sys.exit(1)
    with open(report_path, "r", encoding="utf-8") as f:
        analysis = f.read()
    print(f"📄 读取分析报告: {report_path}")

    # 2. 读取 K 线数据
    csv_path = os.path.join(DATA_DIR, f"btc_klines_{interval}.csv")
    try:
        header, rows = read_csv(csv_path)
    except FileNotFoundError:
        print(f"❌ 找不到数据文件: {csv_path}")
        sys.exit(1)
    print(f"📊 读取 {len(rows)} 根{label}K 线")

    # 3. 加载交易信号提示词
    prompt_path = os.path.join(PROMPTS_DIR, "positions_prompt.md")
    system_prompt = load_prompt(prompt_path)

    # 4. 调用 DeepSeek
    print(f"\n🧠 正在生成交易信号...\n")
    user_msg = build_user_message(interval, analysis, header, rows)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_msg},
    ]

    try:
        raw = call_deepseek(api_key, messages)
    except URLError as e:
        print(f"❌ API 调用失败: {e}")
        sys.exit(1)

    # 5. 解析 JSON
    try:
        result = extract_json(raw)
        result["interval"] = interval
        result["timestamp"] = datetime.now(timezone.utc).isoformat()
    except (json.JSONDecodeError, ValueError) as e:
        print(f"❌ JSON 解析失败: {e}")
        print("原始回复:")
        print(raw)
        sys.exit(1)

    # 6. 保存并展示
    save_position(interval, result)

    print("\n" + "=" * 56)
    bias = result.get("bias", "unknown")
    print(f"📈 偏向: {bias.upper()}  |  风险回报比: {result.get('riskReward', 'N/A')}")
    print(result.get("summary", ""))
    print()

    for side in ("long", "short"):
        pos = result.get(side)
        if pos and pos.get("entry"):
            print(f"{'🟢 做多' if side == 'long' else '🔴 做空'}:")
            print(f"   入场: {pos['entry']}")
            print(f"   止损: {pos['stopLoss']}")
            print(f"   止盈: {pos['takeProfit']}")
            print(f"   理由: {pos['reason']}")
            print()
        else:
            print(f"{'🟢 做多' if side == 'long' else '🔴 做空'}: 暂无明确机会\n")
    print("=" * 56)


if __name__ == "__main__":
    main()
