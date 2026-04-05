# Heartbeat 安装与配置指南

Heartbeat 既可以作为 Claude Code Skill 使用，也可以作为 Codex Agent 使用，还能单独作为 Python CLI 工具运行。由于涉及敏感的聊天记录分析，它的核心处理逻辑完全在本地运行，因此除了大语言模型语义分析层外，原始数据绝不会随意上传云端服务器，极大保护了隐私安全。

---

## 🛠️ 方法一：全局安装 (Global Install) —— 【强烈推荐】
全局安装后，你在终端任何位置启动 `claude` 或 `codex`，都能直接调用 Heartbeat。

**1. 选择宿主并创建全局目录**

Claude Code:
```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
```

Codex:
```bash
mkdir -p ~/.codex/skills
cd ~/.codex/skills
```

**2. 将项目 Clone 到本地**
```bash
# 请将地址替换为你自己的 GitHub 地址（如果已 Fork）
git clone https://github.com/your-username/heartbeat.git
```

**3. 安装基础依赖项**
Heartbeat 极为克制地只引入了处理双层折线图必需的 `matplotlib` 以及数据处理常用的 `numpy`，其余解析模块均为纯原生。
```bash
cd heartbeat
pip install -r requirements.txt
```

---

## 📁 方法二：项目级安装 (Local Project Install)
如果你不希望全局挂载，只想在当前工作区里使用它：

Claude Code:
```bash
# 在你当前的工作目录下创建专用的组件目录
mkdir -p .claude/skills

# 克隆并安装
git clone https://github.com/your-username/heartbeat.git .claude/skills/heartbeat
cd .claude/skills/heartbeat
pip install -r requirements.txt
```

Codex:
```bash
mkdir -p .codex/skills
git clone https://github.com/your-username/heartbeat.git .codex/skills/heartbeat
cd .codex/skills/heartbeat
pip install -r requirements.txt
```

---

## ✅ 验证是否安装成功

Claude Code:
1. 关闭当前正在运行的 Claude Code 会话（在终端按下 `Ctrl+D` 或 `exit`）
2. 重新输入 `claude` 启动该环境
3. 输入斜杠 `/` 调出交互式命令菜单，开始向下翻找
4. 如果能看到包含 `将千万条聊天记录，还原成你们心跳共振的轨迹` 介绍语的 Heartbeat 指令块，说明配置成功

Codex:
1. 关闭当前正在运行的 Codex 会话
2. 重新输入 `codex` 启动新会话
3. 在对话中直接输入 `使用 $heartbeat 分析我和 TA 的聊天记录`
4. 如果 Codex 能识别 `Heartbeat` Agent 并进入分析流程，说明配置成功

当前仓库里，`SKILL.md` 用于 Claude Code，`agents/openai.yaml` 用于 Codex。两者共享同一套 `tools/` 与 `prompts/`。
