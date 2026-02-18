#!/usr/bin/env bash
# Quick setup for Claude Code + Routin API
# Usage: run from this directory, or: bash /path/to/setup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${HOME}/.claude"

echo "==> Claude Code + Routin 开发环境快速设置"
echo ""

# 1. Create ~/.claude
mkdir -p "$CLAUDE_DIR"
chmod 700 "$CLAUDE_DIR" 2>/dev/null || true
echo "    [OK] $CLAUDE_DIR"

# 2. settings.json: copy template only if not present
if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
  cp "$SCRIPT_DIR/claude/settings.json.template" "$CLAUDE_DIR/settings.json"
  echo "    [OK] 已创建 settings.json（请填入 Routin API Key）"
else
  echo "    [--] settings.json 已存在，未覆盖"
fi

# 3. config.json: copy if not present
if [ ! -f "$CLAUDE_DIR/config.json" ]; then
  cp "$SCRIPT_DIR/claude/config.json" "$CLAUDE_DIR/config.json"
  echo "    [OK] 已创建 config.json"
else
  echo "    [--] config.json 已存在，未覆盖"
fi

echo ""
echo "==> 下一步："
echo "    1. 获取 API Key: https://routin.ai → 钱包/个人 → 创建密钥"
echo "    2. 编辑并填入 Key: nano $CLAUDE_DIR/settings.json"
echo "       将 PASTE_YOUR_ROUTIN_API_KEY_HERE 替换为你的 key（如 sk-... 或 ak-...）"
echo "    3. 在项目根目录安装并运行: npm install && npx claude --version"
echo ""
echo "    详细说明见: $SCRIPT_DIR/docs/access-claude-code-routin.md"
echo ""
