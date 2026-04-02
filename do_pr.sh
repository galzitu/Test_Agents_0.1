#!/bin/bash
# ============================================================
# Auto-PR script — Trading Agent v2 upgrade
# Run this from the trading-agent folder: bash do_pr.sh
# ============================================================

set -e  # Stop on any error

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "📂 Working in: $REPO_DIR"

# ── Check git ──────────────────────────────────────────────
if ! git rev-parse --git-dir > /dev/null 2>&1; then
  echo "❌ Not a git repo. Initializing..."
  git init
  git remote add origin https://github.com/galzitu/Test_Agents_0.1.git
fi

echo "🔍 Current status:"
git status --short

# ── Create branch ──────────────────────────────────────────
BRANCH="feature/trading-agent-v2-research-upgrade"
echo ""
echo "🌿 Creating branch: $BRANCH"
git checkout -b "$BRANCH" 2>/dev/null || git checkout "$BRANCH"

# ── Stage all changes ──────────────────────────────────────
git add -A
echo ""
echo "📦 Files to commit:"
git diff --cached --stat

# ── Commit ────────────────────────────────────────────────
echo ""
echo "💾 Committing..."
git commit -m "feat: trading agent v2 — GT-Score scoring, ATR sizing, bug fixes

Major upgrades based on top-trader research (NotebookLM):

🔬 Scoring System v2.0 (GT-Score inspired):
  - Weights: 30/25/20/15/10 (win rate/PF/RR/consistency/drawdown)
  - New: consistency metric (penalizes outlier-dependent strategies)
  - New: max drawdown metric (survivability measure)

📐 ATR-Based Position Sizing (risk_manager.py):
  - Position_Size = Risk_Budget / Risk_Per_Share
  - Risk_Per_Share = |entry - stop_loss| or ATR × 1.5 fallback
  - Auto-shrinks positions in volatile conditions

📊 Strategy Upgrades:
  - All 9 strategies now pass ATR in indicators dict
  - EMA Cross: ATR-based stops (was static EMA21)
  - orb, vwap, volume_spike, bollinger: ATR added

🐛 Bug Fixes:
  - SQL injection: LIMIT clause sanitized with int() (memory.py)
  - ET timezone: all 5 date.today() → _today_et() (memory.py)
  - Startup crash: _log_startup_info() wrapped in try/except (core.py)
  - Log timezone: log file uses ET not local time (main.py)

🔧 New Tools:
  - watchdog.sh: auto-restart if agent dies during market hours
  - scripts/reconcile_trades.py: sync missing trades from Alpaca

📚 Research Skill:
  - .claude/skills/trading-expert/SKILL.md with full top-trader knowledge

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"

echo ""
echo "✅ Committed!"

# ── Push ──────────────────────────────────────────────────
echo ""
echo "🚀 Pushing to GitHub..."
git push origin "$BRANCH" --set-upstream

# ── Create PR ─────────────────────────────────────────────
echo ""
echo "📬 Creating Pull Request..."

if command -v gh &> /dev/null; then
  PR_URL=$(gh pr create \
    --repo galzitu/Test_Agents_0.1 \
    --base main \
    --head "$BRANCH" \
    --title "feat: Trading Agent v2 — GT-Score scoring + ATR position sizing + bug fixes" \
    --body "$(cat <<'PRBODY'
## 🚀 Trading Agent v2 — Full Research Upgrade

Based on deep trading research (NotebookLM notebook with 123+ sources).

---

## 🔬 Scoring System v2.0 (GT-Score Inspired)

Previous weights: **40/35/25** (win rate / profit factor / risk-reward)
New weights: **30/25/20/15/10** — added two new metrics:

- **Consistency (15%)** — penalizes strategies that depend on rare outlier wins
- **Max Drawdown (10%)** — survivability check

> Research finding: GT-Score improves strategy generalization by 98% vs Sharpe/Sortino

## 📐 ATR-Based Position Sizing

New formula: `Position_Size = Risk_Budget / Risk_Per_Share`

- `Risk_Per_Share` = `|entry_price - stop_loss|` (actual distance to stop)
- Fallback: `ATR × 1.5` if no stop set
- **Effect**: Volatile stocks automatically get smaller positions

## 📊 Strategy Upgrades (9 strategies)

| Strategy | Change |
|---|---|
| EMA Cross | ATR-based stops replacing static EMA(21) |
| All others | ATR now passed in `indicators` dict |

## 🐛 Critical Bug Fixes

| Bug | File | Fix |
|---|---|---|
| SQL injection | `memory.py` | `int()` sanitization on LIMIT |
| Wrong trading date | `memory.py` | `_today_et()` (ET timezone) |
| Startup crash | `core.py` | try/except around startup methods |
| Log filename timezone | `main.py` | ET timezone for log date |

## 🔧 New Tools

- **`watchdog.sh`** — auto-restarts agent if it dies during market hours
- **`scripts/reconcile_trades.py`** — syncs missing trades from Alpaca API

## ⚙️ Setup (run once)

```bash
# Watchdog cron (auto-restart during market hours):
*/5 9-16 * * 1-5 ~/path/to/trading-agent/watchdog.sh

# Sync missing trades:
python scripts/reconcile_trades.py --days 7
```

---
🤖 Generated with [Claude Cowork](https://claude.ai) + NotebookLM trading research
PRBODY
)")
  echo ""
  echo "✅ Pull Request created!"
  echo "🔗 $PR_URL"
else
  echo ""
  echo "⚠️  gh CLI not installed. PR not created automatically."
  echo ""
  echo "To create PR manually, go to:"
  echo "https://github.com/galzitu/Test_Agents_0.1/compare/$BRANCH?expand=1"
fi

echo ""
echo "🎉 Done!"
