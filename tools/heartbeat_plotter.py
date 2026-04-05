#!/usr/bin/env python3
"""
heartbeat_plotter.py — 好感度双折线图生成器

用法：
    python3 heartbeat_plotter.py --scores scores.json --me "小明" --them "小红" --output heartbeat.png
    python3 heartbeat_plotter.py --scores scores.json --me "我" --them "TA" --output heartbeat.png --dark
"""

import json
import argparse
import os
import sys
import tempfile
from pathlib import Path
from datetime import datetime

try:
    os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    import matplotlib.font_manager as fm
except ImportError:
    print("错误：缺少依赖。请运行：pip install matplotlib numpy", file=sys.stderr)
    sys.exit(1)

# ── CJK 字体自动检测（Linux / macOS 均适用）
def _set_cjk_font():
    candidates = [
        "WenQuanYi Micro Hei", "WenQuanYi Zen Hei",
        "Noto Sans CJK SC", "Noto Sans SC",
        "Source Han Sans CN", "Source Han Sans SC",
        "SimHei", "Microsoft YaHei", "PingFang SC",
        "Heiti SC", "STHeiti",
    ]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            matplotlib.rcParams["font.family"] = name
            return
    # 没找到任何中文字体时，suppress 警告
    import warnings
    warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

_set_cjk_font()

THEME_LIGHT = {
    "bg": "#FAFAFA", "panel_bg": "#FFFFFF", "text": "#1A1A2E",
    "subtext": "#6B7280", "grid": "#E5E7EB", "me_color": "#4F6BED",
    "them_color": "#E95A7C", "event_line": "#F59E0B", "zone_50": "#9CA3AF",
}
THEME_DARK = {
    "bg": "#0F111A", "panel_bg": "#1A1D2E", "text": "#E2E8F0",
    "subtext": "#94A3B8", "grid": "#2D3047", "me_color": "#6C8EF5",
    "them_color": "#F472A0", "event_line": "#FBBF24", "zone_50": "#6B7280",
}


def parse_dates(labels):
    parsed = []
    for lbl in labels:
        try:
            parsed.append(datetime.strptime(lbl, "%Y-%m-%d"))
        except ValueError:
            parsed.append(None)
    return parsed


def plot_curve(scores, me_name, them_name, output_path, dark=False, title=None):
    t = THEME_DARK if dark else THEME_LIGHT
    labels    = [s["label"] for s in scores]
    me_vals   = [s["me"]   for s in scores]
    them_vals = [s["them"] for s in scores]
    dates = parse_dates(labels)
    use_dates = all(d is not None for d in dates)
    x = dates if use_dates else list(range(len(labels)))

    fig, ax = plt.subplots(figsize=(14, 6), facecolor=t["bg"])
    ax.set_facecolor(t["panel_bg"])

    ax.fill_between(x, me_vals,   alpha=0.15, color=t["me_color"],   linewidth=0)
    ax.fill_between(x, them_vals, alpha=0.12, color=t["them_color"], linewidth=0)
    ax.plot(x, me_vals,   color=t["me_color"],   linewidth=2.5, label=f"我 ({me_name})",
            marker="o", markersize=4, zorder=3)
    ax.plot(x, them_vals, color=t["them_color"], linewidth=2.5, label=f"TA ({them_name})",
            marker="o", markersize=4, zorder=3)
    ax.axhline(50, color=t["zone_50"], linewidth=1, linestyle="--", alpha=0.5, label="中性基线 (50)")

    # 事件标注
    for i, s in enumerate(scores):
        if s.get("events"):
            ex = x[i]
            ax.axvline(ex, color=t["event_line"], linewidth=1.2, linestyle=":", alpha=0.8)
            for j, evt in enumerate(s["events"]):
                ax.annotate(
                    evt,
                    xy=(ex, max(me_vals[i], them_vals[i])),
                    xytext=(8, 8 + j * 14),
                    textcoords="offset points",
                    fontsize=8, color=t["event_line"],
                    arrowprops=dict(arrowstyle="->", color=t["event_line"], lw=0.8, alpha=0.7),
                )

    ax.set_ylim(0, 100)
    ax.set_ylabel("好感度", color=t["subtext"], fontsize=11)
    ax.tick_params(colors=t["subtext"])
    for spine in ax.spines.values():
        spine.set_edgecolor(t["grid"])
    ax.grid(axis="y", color=t["grid"], linewidth=0.7, alpha=0.8)

    if use_dates:
        n = len(dates)
        fmt = "%m-%d" if n <= 30 else ("%m/%d" if n <= 60 else "%y-%m")
        ax.xaxis.set_major_formatter(mdates.DateFormatter(fmt))
        fig.autofmt_xdate(rotation=30, ha="right")
    else:
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.tick_params(axis="x", colors=t["subtext"])

    chart_title = title or f"好感度曲线分析：{me_name} ↔ {them_name}"
    ax.set_title(chart_title, color=t["text"], fontsize=14, fontweight="bold", pad=16)
    ax.legend(loc="upper right", framealpha=0.85, facecolor=t["panel_bg"],
              edgecolor=t["grid"], labelcolor=t["text"], fontsize=10)

    me_avg   = round(sum(me_vals) / len(me_vals), 1)
    them_avg = round(sum(them_vals) / len(them_vals), 1)
    stat_text = f"平均好感度  我:{me_avg}  TA:{them_avg}\n共 {len(scores)} 个时间段"
    ax.text(0.01, 0.02, stat_text, transform=ax.transAxes, fontsize=8.5,
            color=t["subtext"], verticalalignment="bottom",
            bbox=dict(facecolor=t["panel_bg"], alpha=0.6, edgecolor="none", boxstyle="round,pad=0.3"))

    plt.tight_layout(pad=1.5)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", facecolor=t["bg"])
    plt.close(fig)
    print(f"✅ 图表已生成：{out_path}")


def main():
    parser = argparse.ArgumentParser(description="好感度折线图生成器")
    parser.add_argument("--scores", required=True)
    parser.add_argument("--me",     required=True)
    parser.add_argument("--them",   required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--dark",   action="store_true")
    parser.add_argument("--title",  default=None)
    args = parser.parse_args()

    scores = json.loads(Path(args.scores).read_text(encoding="utf-8"))
    if not scores:
        print("错误：评分数据为空。", file=sys.stderr); sys.exit(1)

    plot_curve(scores, args.me, args.them, args.output, dark=args.dark, title=args.title)


if __name__ == "__main__":
    main()
