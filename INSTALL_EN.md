# Heartbeat Installation & Configuration Guide

Heartbeat can be used as a Claude Code Skill and also directly as a Python CLI tool. Since it handles highly sensitive chat logs, its core extraction and plotting logic effectively runs locally on your machine—so, apart from the implicit LLM semantic scoring, your raw database records are kept extremely private and secure.

---

## 🛠️ Method 1: Global Installation (Highly Recommended)
With a global installation, you can launch `claude` from anywhere in your file system and the `/heartbeat` command will always be readily available.

**1. Create and enter the global `.claude/skills` directory**
```bash
mkdir -p ~/.claude/skills
cd ~/.claude/skills
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
If you prefer not to install it globally and only want Heartbeat specific to your current terminal workspace:

```bash
# Create the local skills directory in your current workspace
mkdir -p .claude/skills

# Clone and install dependencies
git clone https://github.com/your-username/heartbeat.git .claude/skills/heartbeat
cd .claude/skills/heartbeat
pip install -r requirements.txt
```

---

## ✅ Verifying the Installation

1. Safely exit any currently running Claude Code session (hit `Ctrl+D` or type `exit` in the terminal).
2. Type `claude` to boot up a fresh session.
3. Bring up the command menu by typing the forward slash `/`.
4. Look through the options—if you explicitly see the `/heartbeat` command alongside our poetic "trajectory of your resonating heartbeats" introduction, you're all set!

Once correctly installed, simply type `/heartbeat-review` to analyze a past romance or `/heartbeat-track` to track an ongoing one.
