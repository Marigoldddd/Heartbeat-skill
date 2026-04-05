<div align="center">

# Heartbeat

> *"情绪的起伏，藏在那些没有说出口的停顿里。"*
> *将千万条聊天记录，还原成你们心跳共振的轨迹。*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)
[![Codex](https://img.shields.io/badge/Codex-Agent-10a37f)](agents/openai.yaml)

[快速开始](#快速开始) · [使用方式](#使用方式) · [效果展示](#效果展示) · [工作原理](#工作原理) · [详细安装指南](INSTALL.md) · [**English**](README_EN.md)

</div>

Heartbeat 是一个用于分析双人聊天记录的双向好感度曲线工具。

你提供聊天记录，它会输出两类结果：
- 一张双向好感度折线图：按时间窗口展示「我」和「TA」的情绪投入变化
- 一份诊断报告：总结关系阶段、关键拐点、双方画像与整体判断

它既可以作为 Claude Code Skill 使用，也可以作为 Codex Agent 使用，还可以单独当作 Python CLI 工具运行。

## 适合什么场景

- 💔 想复盘一段已经结束或明显降温的关系
- 🌙 想持续追踪一段正在进行中的互动变化
- 🧭 想把“感觉不对劲”转成可回看的时间线和结构化报告

## 输入与输出

**输入**
- 💬 微信导出的 `.txt` / `.html` / `.csv`
- 🍎 iMessage 导出文件
- 📱 Android SMS 备份 XML
- ✍️ 直接粘贴的纯文本聊天记录

**输出**
- 📈 `heartbeat.png`：双向好感度折线图
- 📝 `report.md`：文字诊断报告
- 🗂️ `scores.json` / `parsed.json`：中间评分与解析结果，便于继续追踪或二次处理

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

> Claude Code / Codex 的挂载方式与全局安装步骤见 [INSTALL.md](INSTALL.md)。

### 2. 选择一种使用方式

#### Claude Code

```text
/heartbeat-review    复盘一段已结束或降温的关系
/heartbeat-track     建立持续追踪
/heartbeat-update    追加新的聊天记录更新曲线
/heartbeat-list      列出已保存的分析会话
```

#### Codex

```text
使用 $heartbeat 分析我和 TA 的聊天记录，并生成好感度曲线和诊断报告
使用 $heartbeat 建立一个持续追踪会话
使用 $heartbeat 更新已有会话的聊天记录
```

#### 直接用 CLI

```bash
# 1) 解析聊天记录
python3 tools/chat_parser.py --file chat.txt --me "我" --them "TA" --output parsed.json

# 2) 计算双向评分
python3 tools/sentiment_scorer.py --input parsed.json --window week --output scores.json

# 3) 生成折线图
python3 tools/heartbeat_plotter.py --scores scores.json --me "我" --them "TA" --output heartbeat.png

# 4) 生成文字报告
python3 tools/report_writer.py --scores scores.json --parsed parsed.json \
  --me "我" --them "TA" --mode review --output report.md
```

## 使用方式

这个仓库同时提供三种入口：

- 🤖 `SKILL.md`：Claude Code Skill 定义
- 🧠 `agents/openai.yaml`：Codex Agent 描述
- 🛠️ `tools/*.py`：可单独调用的本地 Python 工具链

如果你只是想尽快跑起来，优先用 Claude Code 或 Codex；如果你要接入自己的流程或批处理，再用 CLI。

## 效果展示

### 📈 双向好感度折线图

![示例折线图](examples/sample_heartbeat.png)

### 📝 综合诊断报告示例

> **综合评估**：存在明显的付出不对等现象，长期单方投入更多往往是关系隐患。
> **建议关注的时间节点**：2024-01-04、2024-01-05、2024-01-09

完整报告示例请见 [examples/sample_report.md](examples/sample_report.md)。

## 功能亮点

- 📊 双向量化：同时计算「我」和「TA」的变化，不只判断单方情绪
- 🗓️ 多粒度时间窗口：支持按天、周、月聚合曲线
- 🧾 双输出产物：同时生成可视化折线图和结构化文字报告
- 🔄 两种分析模式：支持复盘型与追踪型会话
- 💬 多格式导入：支持微信、iMessage、SMS XML 和纯文本
- 🔒 本地优先：核心解析、规则评分、绘图和报告写入都在本地完成

## 一个最小闭环

典型流程是这样的：

1. 导入聊天记录
2. 解析成双向消息流
3. 按时间窗口计算双方好感度
4. 生成折线图与报告
5. 将结果写入 `sessions/{slug}/`

生成后的目录结构如下：

```text
sessions/{slug}/
├── heartbeat.png
├── report.md
├── scores.json
├── parsed.json
├── meta.json
└── history/
    ├── heartbeat_v1.png
    └── report_v1.md
```

## 工作原理

Heartbeat 的评分由两层组成：

### 1. 🧠 语义推理层

由大语言模型结合上下文判断真实语气和情绪走向，例如：

- 同一句“随便”是在撒娇、疲惫还是敷衍
- 哪些片段是关系升温或降温的关键转折点
- 在消息太少时主动降低结论置信度

### 2. 📏 行为规则层

基于聊天记录元数据做客观评分：

| 维度 | 子权重 | 说明 |
|------|------|------|
| 主动性 | 25% | 谁更常先发起对话 |
| 回复速度 | 20% | 平均回复延迟，越快通常投入越高 |
| 消息长度 | 15% | 单条消息平均信息量 |
| 情感词密度 | 25% | 正向/负向情感词与表达频率 |
| 特殊行为 | 15% | 反问、emoji、亲昵称呼等特征 |

最终曲线不是简单情绪分类，而是语义理解与行为信号融合后的时间序列。

## 工具链

```text
聊天记录文件
    ↓
tools/chat_parser.py       → parsed.json
    ↓
tools/sentiment_scorer.py  → scores.json
    ↓
tools/heartbeat_plotter.py → heartbeat.png
tools/report_writer.py     → report.md
```

## 隐私说明

- 🔐 聊天记录解析、规则评分、绘图和报告生成都在本地完成
- 🏠 仓库本身不会把原始聊天记录主动上传到外部服务
- ☁️ 如果你通过 Claude Code / Codex 使用语义分析层，是否会把部分文本发送给模型，取决于你当前宿主和模型的实际调用方式

这类数据天然敏感，建议在本地环境中使用，并自行决定是否脱敏。

<div align="center">

*Built for use with Claude Code and Codex*

</div>
