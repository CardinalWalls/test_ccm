# Claude Code + Routin 开发环境快速设置包

一键（或几步）在新机器上搭好 Claude Code，通过 Routin API 调用 Claude 4.5/4.6 模型。

## 内容

- **claude/** — Claude 配置模板
  - `settings.json.template`：Routin API 与模型配置（需填入 API Key）
  - `config.json`：主 API 设为 Routin，避免插件强制登录
- **docs/access-claude-code-routin.md** — 完整说明（安装、Routin 注册、配置、FAQ）
- **setup.sh** — Linux/macOS 快速脚本：创建 `~/.claude` 并写入配置模板
- **package.json.template** — 新项目可复制为 `package.json` 后 `npm install`

## 快速开始（Linux/macOS）

1. 解压本包到任意目录，进入该目录。
2. 运行：
   ```bash
   bash setup.sh
   ```
3. 获取 [Routin](https://routin.ai) API Key，编辑 `~/.claude/settings.json`，将 `PASTE_YOUR_ROUTIN_API_KEY_HERE` 替换为你的 key。
4. 在要用 Claude Code 的项目根目录：
   ```bash
   cp package.json.template package.json   # 若无 package.json
   npm install
   npx claude --version
   npx claude
   ```

## 手动设置（或 Windows）

1. 创建 `~/.claude`（Windows: `%USERPROFILE%\.claude`）。
2. 将 `claude/settings.json.template` 复制为 `~/.claude/settings.json`，填入 API Key。
3. 将 `claude/config.json` 复制为 `~/.claude/config.json`。
4. 项目里安装：`npm install --save-dev @anthropic-ai/claude-code`，使用 `npx claude`。

详见 **docs/access-claude-code-routin.md**。

## 模型说明（当前配置）

| 用途       | 模型 |
|------------|------|
| 默认       | claude-sonnet-4-6 |
| 快速/轻量  | claude-haiku-4-5-20251001 |
| Opus 档位  | claude-opus-4-6 |

API 基地址：`https://api.routin.ai/`

## 版本

- Claude Code: `@anthropic-ai/claude-code@^2.1.45`
- 配置包生成日期：2025-02
