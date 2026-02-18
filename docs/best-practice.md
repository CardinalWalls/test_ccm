
## 干净的最佳实践清单（按你 1/2/3/4/6/7 点落地）

1.2 非交互式：Python subprocess 调度（官方强支持）

你要的“Python subprocess 调度、甚至被另一个 CLI 调度”——完全成立，因为 Claude Code 的 print 模式就是给 automation 用的：

claude -p "..."

--output-format json|stream-json

--json-schema 直接让输出满足你定义的结构（很适合做“plan 批量 review”）

一个最小可用的 Python 例子（同步跑，适合你再包一层 Ralph loop）：

import json, subprocess, textwrap

cmd = [
  "claude",
  "-p",
  "Read TASK.md and return a plan as JSON matching the schema.",
  "--permission-mode", "plan",
  "--tools", "Read,Grep,Glob",
  "--json-schema", json.dumps({
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "steps": {"type": "array", "items": {"type": "string"}},
      "risks": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["title", "steps"]
  }),
  "--output-format", "json",
  "--max-turns", "6"
]

out = subprocess.check_output(cmd, text=True)
plan = json.loads(out)
print(plan["title"])


被 Cursor CLI 调度？对你来说就是：Cursor 那边起进程跑这个命令；Claude Code 不要求 TTY 才能工作（print 模式）。


### A. 把 Claude Code 变成“可控的子进程”（你所有编排的地基）

* **统一入口只用 print/headless**：一律 `claude -p "...prompt..."`，不要依赖交互 TUI。([Claude Code][1])
* **强制结构化输出**

  * 做 plan/摘要/审计：`--output-format json --json-schema ...`（输出可回归测试、可批量 review）。([Claude Code][5])
  * 做监控/进度条：`--output-format stream-json --verbose --include-partial-messages`（逐行 JSON 事件流）。([Claude Code][5])
* **给每次调用设“熔断器”**：`--max-turns` +（可选）`--max-budget-usd`，防止 runaway。([Claude Code][1])

### B. 权限策略：吞吐量提升靠它，但也最容易翻车

* **默认优先用白名单免询问**：`--allowedTools ...`（比如 Read/Edit/Bash(git …)/Bash(test …)）。([Claude Code][1])
* **仅在隔离沙箱里才用 YOLO**：`--dangerously-skip-permissions`（官方明确“use with caution”）。([Claude Code][1])
* **“免询问 ≠ 工具全开”**：用 `--tools` 限制工具面；用 `--allowedTools` 决定哪些免询问。([Claude Code][1])
* **把“组织级硬约束”放 settings（而不是 prompt）**：settings 支持集中管控 hooks 与 permission rules（managed-only），适合审计/合规。([Claude Code][6])

### C. Ralph loop：用“任务队列 + 退出条件 + 门禁”实现持续吞吐

（这里给的是“最小正确姿势”，不绑定某个具体实现）

* **任务队列必须是显式文件/结构**：比如 `TASKS.md` / `tasks.json` / `issues` 拉取结果；每次只取 1 个任务执行，执行完标记完成，再取下一个。
* **退出条件必须是“双重门控”**：

  1. 队列为空；或
  2. 明确写入 `EXIT_SIGNAL` / `done=true` 之类的结构化标记（避免模型“自宣完成”）
     （现成实现通常会把“退出信号”做成固定约定，你贴文说的就属于这种模式。([GitHub][2])）
* **强制质量门禁的正确挂点是 hooks，不是 prompt**：

  * 用 **Stop hook**：Claude 试图停下时，检查“测试是否通过/是否提交/是否更新 PROGRESS”，不满足就 `decision:"block"` 让它继续。([Claude Code][4])
  * 多 agent 时用 **TeammateIdle**：队友要 idle 时，exit code 2 直接阻止，让它继续补齐门禁。([Claude Code][4])
* **必须防无限循环**：Stop hooks 的输入包含 `stop_hook_active`（表示已经在被 stop hook 推着继续跑），你要用它或读 transcript 来避免永动机。([Claude Code][4])

#### 干活的定义
“##任务生命周期
6.
**领取任务**:原子操作，从data/dev-tasks.json获取任务**创建工作区**
git worktree add -b task/xxx ../voice-notes-worktrees/task-xxx创建隔离的 data/目录(实验数据库)
Symlink 共享文: dev-tasks.json, api-key.json ( PROGRESS.md 禁止 symlink)Symlink node_modules/加速启动分配专属端口
**实现功能**:ClaudeCode 在隔离环境中工作**提交代码**:gitcommit在任务分支**Merge+测试**git fetch origin && git merge origin/mainnpm test**自动合并到 main**
7
8
git fetch origin main'
git rebase origin/main,如果失败，按照下面的"冲突处理"来resolve rebase conflict如果成功，则 git merge main task-xxx && git push origin main,并且 继续执行下一步如果这一步有任何失败，则退回到步骤5**标记完成**:更新 dev-tasks.json (必须在清理之前，防止进程被杀时任务状态丢失)k*
清理
**
+删除本地分支git worktree remove删除远程 task分支
重启 dev server**经验沉淀**:在 PROGRESS.md记录经验教训(可选，如果被杀也不影响任务状态)”

### D. 并行：Git worktree 是“吞吐量倍增器”的标准隔离单元

* **一 agent 一 worktree（强推荐）**：官方文档直接给出“并行 Claude Code 会话”的 worktree 操作与理由。([Claude Code][3])
* **每个 worktree 都要初始化依赖**：npm/pip/venv 等，别让 agent 在“缺依赖”里浪费 5 分钟 turn。([Claude Code][3])
* **worktree 命名与任务绑定**：目录名/分支名带 task-id（便于审计归档与回滚）。
* **容器化时的关键点**：每个 worktree 挂载到独立容器工作目录；必要时给每个容器独立的 Claude 状态卷（避免 session/日志混淆）。

#### 举例
##多实例并行开发(Git Worktree
### 架构说明
支持多个ClaudeCode 实例并行工作，每个实例在独立的 git worktree中执行任务。
并行开发工作流
Worker 1port:5200worktree
data/
Worker 2
port:5201worktree
data/
Worker 3
port:5202
worktree
data/
(隔离的实验数据)
共享文件(symlink):
- dev-tasks.json(任务队列)
dev-task.lock(文件)api-key.json (API 密钥)
禁止 symlink:PROGRESS.md(直接用 git-C编辑主仓库文件)
公
#### 冲突处理
冲突处理
**Rebase 失败时的处理流程**:
1如果是"unstaged changes"错误，先 commit 或 stash 当前改动
2.如果有 merge conflicts:
    1. 运行 `git status`，查看所有有冲突的文件
    2. 依次打开每个冲突文件，理解双方的修改内容和意图
    3. 手动编辑文件，保留和整合正确的更改，删除冲突标记
    4. 保存修改后，执行 `git add <已解决的文件>`
    5. 执行 `git rebase --continue` 继续 rebase 流程
    6. 如果还有冲突，重复上述步骤，直到 rebase 全部完成
    
**测试失败时的处理流程**:
1运行测试:npmtest
2如果失败，分析错误信息
3修复代码中的 bug
4重新运行测试，直到全部通过
5提交修复:git commit -m"fix:
**不要放弃**:遇到rebase或测试失败时，必须解决问题后才能继续众能直渊咒势奖。

### E. 监控与审计：两条流同时要

* **证据链（落盘）**：hooks 的 stdin 含 `transcript_path`（JSONL），能作为审计原始材料；subagent 也有独立 transcript 路径。([Claude Code][4])
* **运行态（实时）**：用 stream-json 做“manager 监控面板/告警”，只消费 stdout 的 JSON 行。([Claude Code][5])
* **hook 输入输出规范化**：hooks 通过 stdin 收 JSON、用 exit code/stdout/stderr 控制行为；exit code 2 是“阻止动作”的统一语义（不同事件效果不同）。([Claude Code][4])
* **把“噪声”打到 stderr**：stdout 留给 JSON（否则你 manager 的 JSON parser 会被污染）。
“claude -p [prompt] --dangerously-skip-permissions \       --output-format stream-json --verbose”
这样我的 Claude Code manager 就能通过检查 json 格式的 log 去发现它正在管理的某个 CC 实例到底哪里出了问题，并据此提升它的管理能力

#### 经验沉淀 （这里也可以用claude insights）
经验教训沉淀每次遇到问题或完成重要改动后，要在遇到了什么问题如何解决的
以后如何避免
**必须附上 git commit ID**
**同样的问题不要犯两次!**



### F. Plan 批量 kickoff + 统一 review：用 JSON Schema 把“可审查性”做实

* **Plan 只允许读/分析**：`--permission-mode plan` + `--tools "Read,Grep,Glob"`（或你需要的最小集合）。([Claude Code][1])
* **Plan 输出必须结构化**：`--output-format json --json-schema ...`，字段至少包含：`tasks[] / acceptance[] / risks[] / estimate`。([Claude Code][5])
* **Plan farm 并发跑**：外层用 Python/并行框架同时起 N 个 `claude -p`，收集 JSON 后统一 review（机器能 diff、能打分、能落库）。([Claude Code][5])
* **通过后再进入执行 loop**：执行环节再放开 `--allowedTools` 或沙箱 YOLO（别让执行环节“边想边改”污染方案质量）。

#### 这里 Claude Code 其实给了你“三件套”

--permission-mode plan：一开始就进入 plan 模式

--tools "Read,Grep,Glob"（或更严格 --tools ""）：限制它只能分析，不让它改

--json-schema + --output-format json：让每个 plan 都输出成结构化对象，方便批量 review

一个“批量产出 plans”的命令模板：

claude -p "Read TASK.md and output an implementation plan." \
  --permission-mode plan \
  --tools "Read,Grep,Glob" \
  --json-schema '{"type":"object","properties":{"title":{"type":"string"},"steps":{"type":"array","items":{"type":"string"}},"estimate":{"type":"string"}},"required":["title","steps"]}' \
  --output-format json \
  --max-turns 6


然后你在外层并发跑 N 个（Python multiprocessing / GNU parallel / 你自己的 orchestrator），收集 JSON 做统一 review。

如果你想更“内建并行”，Claude Code 的 agent teams + --teammate-mode tmux 也能把多个子会话组织起来。
再配合 TeammateIdle hook，你甚至能做“计划必须过审/测试必须通过才允许 idle”的门禁。

---

## 一个“最小黄金配置”（建议你按这个当默认模板）

1. **Plan 阶段（批量）**：`--permission-mode plan` + `--output-format json --json-schema` + `--max-turns 2~4`。([Claude Code][1])
2. **Exec 阶段（单任务）**：`claude -p ... --allowedTools ... --max-turns ...`（优先白名单免询问）。([Claude Code][5])
3. **Autopilot（持续跑）**：Ralph loop（任务队列）+ Stop/TeammateIdle hooks（门禁与“不得自宣完成”）。([Claude Code][4])
4. **并行扩展**：worktree × N（每个 worktree 一个 agent/容器）。([Claude Code][3])
5. **审计**：transcript_path 全量归档 + stream-json 实时监控。([Claude Code][4])

---

## 审计结论（先纠错 + 定界）

1. **Claude Code 的“非交互式/可编排”是官方一等公民**：`claude -p`、`--output-format json|stream-json`、`--include-partial-messages`、`--json-schema`、`--max-turns`、`--max-budget-usd` 这些都是官方 CLI 能力，适合被 Python subprocess / CI / 另一个 CLI 调度。([Claude Code][1])
2. **“跳过 permission 询问”是官方支持的，但必须放在隔离环境里做**：`--dangerously-skip-permissions` 明确存在；更稳的是用 `--allowedTools` 做白名单免询问。([Claude Code][1])
3. **Ralph loop：不是 Claude Code 官方内置功能，但确实有“现成实现/脚手架”**（社区工具 + 标准化目录/命令），并且你贴文描述的 `ralph-enable / ralph --monitor` 这类能力在现成 repo 里能看到。([GitHub][2])
4. **并行最推荐的隔离单位是 Git worktree**：官方文档直接把“并行 Claude Code 会话”写成 worktree 工作流。([Claude Code][3])
5. **审计/监控的“证据链”抓手是 hooks + transcript_path + stream-json**：hooks stdin 里含 `transcript_path`，并支持阻止停止（Stop）或阻止队友 idle（TeammateIdle 通过 exit code 2）。([Claude Code][4])
---
[1]: https://code.claude.com/docs/en/cli-reference "CLI reference - Claude Code Docs"
[2]: https://github.com/frankbria/ralph-claude-code?utm_source=chatgpt.com "frankbria/ralph-claude-code: Autonomous AI development ..."
[3]: https://code.claude.com/docs/en/common-workflows "Common workflows - Claude Code Docs"
[4]: https://code.claude.com/docs/en/hooks "Hooks reference - Claude Code Docs"
[5]: https://code.claude.com/docs/en/headless "Run Claude Code programmatically - Claude Code Docs"
[6]: https://code.claude.com/docs/en/settings "Claude Code settings - Claude Code Docs"
