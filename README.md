<div align="center">

# Heartbeat

> *"情绪的起伏，藏在那些没有说出口的停顿里。"*
> *将千万条聊天记录，还原成你们心跳共振的轨迹。*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)

[效果展示](#效果展示) · [功能](#功能) · [详细安装指南](INSTALL.md) · [快速开始](#快速开始) · [**English**](README_EN.md)

</div>

---

## 效果展示

### 双向好感度折线图
![示例折线图](examples/sample_heartbeat.png)

### 综合诊断报告示例
> **综合评估**：对方好感度在下滑，而我方仍在投入，这种错位是关系恶化的常见前兆。
> **建议关注的时间节点**：2024-01-15：我方 -5.0 / 对方 -22.0

完整报告示例请见 [examples/sample_report.md](examples/sample_report.md)

---

## 功能

- 📊 **双向量化** — 同时分析「我」和「TA」的好感度变化，而不是只看对方
- 📈 **折线图** — 按周/月/天分段，生成好感度双折线图（PNG, 300 DPI）
- 📝 **文字报告** — 关系概况、关键节点、双方行为画像、整体诊断
- 🔄 **两种模式** — 复盘型（已结束关系）和追踪型（持续更新）
- 💬 **多格式支持** — 微信 TXT/HTML/CSV、iMessage、SMS XML、纯文本粘贴

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```
> 完整 Claude Code 挂载步骤与全局安装说明，请务必参考 **[详细安装指南](INSTALL.md)**。

### 在 Claude Code 中使用

```
/heartbeat-review    ← 复盘一段已结束的关系
/heartbeat-track     ← 追踪正在进行的关系
/heartbeat-update    ← 追加新的聊天记录更新曲线
/heartbeat-list      ← 列出所有已保存的分析会话
```

## 工具链

```
聊天记录文件
    ↓
tools/chat_parser.py      → parsed.json    (双向消息列表 + 特征提取)
    ↓
tools/sentiment_scorer.py → scores.json    (按时间窗口的双向好感度评分)
    ↓
tools/heartbeat_plotter.py    → heartbeat.png      (双折线图)
tools/report_writer.py    → report.md      (文字诊断报告)
```

## 双层评分模型

Heartbeat 的每一次打分，都由以下两层维度加权融合而成：

### 一、Claude 语义推理（核心权重 80%）
由 Claude 模型深度参与，根据上下文真实语境进行理解：
- 识别潜台词与真实情绪（比如 "随便" 是在撒娇还是在敷衍）
- 自动捕捉长对话中的核心情感事件与爆发拐点
- 在消息量过少的日期自动降低置信度，交由规则接管

### 二、客观行为规则（客观权重 20%）
基于聊天记录元数据的硬性、可量化指标分析：

| 维度 | 子权重 | 说明 |
|------|------|------|
| 主动性 | 25% | 谁先发消息 / 每天主动发起对话的次数占比 |
| 回复速度 | 20% | 双方的平均回复延迟（越快越高分） |
| 消息长度 | 15% | 平均消息字符丰富度（字数越多 → 投入越多） |
| 情感词密度 | 25% | 命中词库中正向/负向情感特征词频率 |
| 特殊行为 | 15% | 主动反问次数、emoji密度、专属亲昵称呼 |

## 会话文件结构

```
sessions/{slug}/
├── heartbeat.png   ← 好感度双折线图
├── report.md       ← 完整分析报告
├── scores.json     ← 时间窗口评分数据
├── parsed.json     ← 解析后的消息数据
├── meta.json       ← 会话元信息
└── history/        ← 历史版本备份
    ├── heartbeat_v1.png
    └── report_v1.md
```

## 单独使用工具

```bash
# 解析双向聊天记录
python3 tools/chat_parser.py --file chat.txt --me "小明" --them "小红" --output parsed.json

# 计算好感度评分
python3 tools/sentiment_scorer.py --input parsed.json --window week --output scores.json

# 生成折线图
python3 tools/heartbeat_plotter.py --scores scores.json --me "小明" --them "小红" --output heartbeat.png

# 生成文字报告
python3 tools/report_writer.py --scores scores.json --parsed parsed.json \
  --me "小明" --them "小红" --mode review --output report.md
```

<div align="center">

*Built for use with Claude Code*

</div>
