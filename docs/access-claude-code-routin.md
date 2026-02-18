# Access Claude Code via Routin API

This guide walks through installing and configuring Claude Code locally so it calls AI models via the [Routin API](https://routin.ai) platform.  
Source: [Routin Docs – Use Claude Code](https://docs.routin.ai/en/docs/DeveloperTools/access-claude-code).

---

## Requirements

- **Git:** 2.20.0+
- **npm:** 8.0.0+
- **Node.js:** 18.0.0+
- **OS:** macOS 10.15+ / Ubuntu 18.04+ / Windows 10+

---

## Part 1: Install Claude Code

### Option 1: Install globally with npm

```bash
# Check Node.js version
node --version

# Install Claude Code globally
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version
```

### Option 2: Install per project (this repo)

```bash
# Run in your project root
npm install --save-dev @anthropic-ai/claude-code

# Use npx
npx claude --version
```

**This project uses Option 2.** After install, use `npx claude` in the project root.

### Common install issues

1. **Permission issues (macOS/Linux)**

   ```bash
   sudo npm install -g @anthropic-ai/claude-code
   # Or change npm default prefix
   npm config set prefix ~/.npm-global
   export PATH=~/.npm-global/bin:$PATH
   ```

2. **Network issues**

   ```bash
   npm config set registry https://registry.npmmirror.com
   npm install -g @anthropic-ai/claude-code
   ```

---

## Part 2: Routin API setup

### Register and authenticate

1. **Visit:** [https://routin.ai](https://routin.ai)
2. **Sign in with Gitee:** Click “Gitee 登录” at bottom right; a Routin account is created and Gitee is authorized.
3. **Top up:** After login, go to “Wallet/Personal” and choose “Top up balance”.

### Get an API key

1. **Create the key** in the Routin dashboard (unlimited quota, no expiry; leave group settings empty for now).
2. **Configure the key** in Claude Code as below.

---

## Part 3: Claude Code configuration

### Create the config directory

```bash
mkdir -p ~/.claude
chmod 700 ~/.claude   # Linux/macOS
```

### Edit the config file

- **Linux/macOS:** `nano ~/.claude/settings.json` or `code ~/.claude/settings.json`
- **Windows:** `cd ~/.claude/` then open the folder in VS Code and create `settings.json`.

### Base config template

Replace `sk-your-api-key-here` with your Routin API key.

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-your-api-key-here",
    "ANTHROPIC_BASE_URL": "https://api.routin.ai/",
    "ANTHROPIC_MODEL": "claude-sonnet-4-6",
    "ANTHROPIC_SMALL_FAST_MODEL": "claude-haiku-4-5-20251001",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-4-6",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-4-6",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001"
  },
  "alwaysThinkingEnabled": true
}
```

### Skip login (required for newer versions)

Claude Code v2.x shows a login/onboarding screen by default. To use Routin instead, you must set `hasCompletedOnboarding: true`.

**Linux / macOS / WSL:** Create or edit `~/.claude.json` and add:

```json
{ "hasCompletedOnboarding": true }
```

If the file already exists (e.g. with cached features), append this key to the JSON object:

```json
"hasCompletedOnboarding": true
```

**Windows:** Create `C:\Users\<YourUser>\.claude.json` with the same content.

Without this, Claude Code stays on the login screen and never reads your Routin API settings.

---

## Your turn: set your API key

Setup is done except for your key. Do this once:

1. Get your API key from [Routin](https://routin.ai) (Wallet/Personal → create key).
2. Open the config file:
   ```bash
   nano ~/.claude/settings.json
   ```
   or in an editor: `~/.claude/settings.json`
3. Replace `sk-your-api-key-here` with your real key (e.g. `ak-...` or `sk-...`). Save.
4. Test: from this project root run `npx claude` and say "Hello, please introduce yourself".

---

## Part 4: Verify and test

```bash
# Version check (per-project: use npx)
npx claude --version

# Interactive test
npx claude
```

In interactive mode, try: **"Hello, please introduce yourself"**.

---

## FAQ

### Windows: “No suitable shell found”

If you see:

```text
Error: No suitable shell found. Claude CLI requires a Posix shell environment.
```

1. Install [Git for Windows](https://gitforwindows.org/).
2. Set:
   ```bash
   CLAUDE_CODE_GIT_BASH_PATH="C:\\Program Files\\Git\\bin\\bash.exe"
   ```

### Stuck on login / 3rd‑party platforms screen

If Claude Code shows the login screen or "Using 3rd-party platforms" instead of connecting to Routin:

1. Add `hasCompletedOnboarding: true` to `~/.claude.json` (see "Skip login" above).
2. Create `~/.claude/config.json` with:
   ```json
   { "primaryApiKey": "Routin" }
   ```
3. Restart Claude Code.

---

## Get help

- Web: [https://routin.ai](https://routin.ai)
- Docs: [https://docs.routin.ai/en/docs/DeveloperTools/access-claude-code](https://docs.routin.ai/en/docs/DeveloperTools/access-claude-code)
