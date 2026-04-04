# Heartbeat 安装与配置指南

Heartbeat 作为一个 Claude Code Skill，也可单独作为 Python CLI 工具使用。由于涉及敏感的聊天记录分析，它的核心处理逻辑完全在本地运行，因此除了大语言模型语义分析层外，原始数据绝不会随意上传云端服务器，极大保护了隐私安全。

---

## 🛠️ 方法一：全局安装 (Global Install) —— 【强烈推荐】
全局安装后，你在终端任何位置启动 `claude`，都可随时呼叫 `/heartbeat`。

**1. 首先确保存在全局 Skill 存放目录，并进入该目录**
```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
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
如果你不希望全局挂载，只想在这个特定的命令行工作区里使用它：

```bash
# 在你当前的工作目录下创建专用的组件目录
mkdir -p .claude/skills

# 克隆并安装
git clone https://github.com/your-username/heartbeat.git .claude/skills/heartbeat
cd .claude/skills/heartbeat
pip install -r requirements.txt
```

---

## ✅ 验证是否安装成功

1. 关闭当前正在运行的任何 Claude Code 会话（在终端按下 `Ctrl+D` 或 `exit`）
2. 重新输入 `claude` 启动该环境
3. 输入斜杠 `/` 调出交互式命令菜单，开始向下翻找
4. 如果能清晰地看到包含 `将千万条聊天记录，还原成你们心跳共振的轨迹` 介绍语的 `/heartbeat` 指令块，恭喜，一切配置已就绪！

一旦顺利触发，你可以通过 `/heartbeat-review` 来复盘已结束的关系，或者 `/heartbeat-track` 来长期追踪当前的对象！
