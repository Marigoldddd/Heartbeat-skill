# Heartbeat Installation & Configuration Guide

Heartbeat can be used as a Claude Code skill, a Codex agent, or directly as a Python CLI tool. Since it handles highly sensitive chat logs, its core extraction and plotting logic effectively runs locally on your machine, so apart from the LLM semantic scoring layer, your raw records remain private.

---

## 🛠️ Method 1: Global Installation (Highly Recommended)
With a global installation, you can launch `claude` or `codex` from anywhere and invoke Heartbeat directly.

**1. Pick your host and create the global directory**

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

**2. Clone the repository**
```bash
# Replace with your own GitHub URL if you have forked the project
git clone https://github.com/your-username/heartbeat.git
```

**3. Install Python dependencies**
Heartbeat intentionally limits its dependencies. It only requires `matplotlib` and `numpy` for crafting those beautiful dual-line charts.
```bash
cd heartbeat
pip install -r requirements.txt
```

---

## 📁 Method 2: Local Project Installation
If you prefer not to install it globally and only want Heartbeat inside the current workspace:

Claude Code:
```bash
# Create the local skills directory in your current workspace
mkdir -p .claude/skills

# Clone and install dependencies
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

## ✅ Verifying the Installation

Claude Code:
1. Exit any running Claude Code session.
2. Start a fresh `claude` session.
3. Open the slash-command menu with `/`.
4. If Heartbeat appears with its description, the setup is complete.

Codex:
1. Exit any running Codex session.
2. Start a fresh `codex` session.
3. Type `Use $heartbeat to analyze my relationship chat history`.
4. If Codex resolves the `Heartbeat` agent and starts the workflow, the setup is complete.

In this repository, `SKILL.md` is the Claude Code entry point and `agents/openai.yaml` is the Codex entry point. Both reuse the same `tools/` and `prompts/`.
