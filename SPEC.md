已对原文档进行格式整理，主要调整如下：

- 添加一级标题，统一标题层级（#、##、###、####）。
- 修复第8节技术选型表格，补全分隔线。
- 所有代码块指定语言（`python`、`bash`、`text`等）。
- 列表项统一使用“-”并正确缩进。
- 保留ASCII架构图但用代码块包裹，避免渲染错乱。
- 修正换行和多余空格，使Markdown渲染清晰。
- 保留所有原内容和编号，未改动任何实质性文字。

以下是整理后的完整规格文档，可直接复制使用。

---

# Coding Agent Harness — 规格说明

> 2026-08-08 | AI4SE 期末项目 A

---

## 1. 问题陈述

**要解决的问题**：开发者调试 Python 代码时需要反复手动运行、查看报错、修改、再运行，这个循环耗时且枯燥。  
**目标用户**：学习 Python 的学生、需要快速验证脚本的开发者。  
**为什么值得做**：将“运行-报错-修复”闭环自动化，让用户只需粘贴代码，agent 自动完成多轮修复直到通过；同时通过护栏和 HITL 机制保证危险操作不会静默执行。

---

## 2. 用户故事

1. **作为用户**，我想粘贴一段有 bug 的 Python 代码，让 agent 自动运行并修复，直到代码能无错执行，这样我不需要手动调试。
2. **作为用户**，我想在 agent 尝试执行危险操作（如删除文件）时收到提示并决定是否批准，这样我对 agent 的行为有最终控制权。
3. **作为用户**，我想看到每一轮的错误类型和修复动作的实时进展，这样我能理解 agent 在做什么。
4. **作为用户**，我想查看历史会话记录，这样我能回顾之前成功修复的案例。
5. **作为用户**，我想通过单条 `docker run` 命令启动整个应用，这样我不需要配置 Python 环境。

---

## 3. 功能规约

### 3.1 Agent 主循环（`harness/agent_loop.py`）

- **输入**：原始 Python 代码字符串、`BaseLM` 实例、最大轮次（默认 8）
- **行为**：
  1. 从 `memory` 加载最近 5 次会话摘要，注入系统提示
  2. 组装消息列表，调用 `lm.complete()`
  3. 解析 LM 响应，提取 `Action`（`run_code` / `write_file` / `shell` / `give_up`）
  4. 调用 `guardrail.check(action)`：
     - `ALLOW` → 调用 `executor.run()`
     - `HITL_REQUIRED` → 返回暂停状态，等待外部（UI）恢复
     - `BLOCK` → 把拒绝原因回灌 LM，继续下一轮
  5. 把 `RunResult` 传给 `classifier.classify()`，得到 `FailureInfo`
  6. 调用 `classifier.get_repair_prompt(failure_info)`，拼入下一轮消息
  7. 调用 `memory.append_round()`
  8. 检查停机条件（见下）
- **输出**：`LoopResult`（`status`: `success`/`failed`/`stall`/`hitl_pause`/`give_up`，`final_code`，`rounds`）
- **停机条件**（任一满足）：
  - `exit_code == 0`
  - 达到最大轮次
  - 连续 3 轮相同 `FailureType`（卡死检测）
  - LM 返回 `give_up` 动作
- **错误处理**：LM 响应解析失败时，回灌格式错误提示最多重试 2 次，仍失败则停机返回 `failed`

### 3.2 LM 抽象层（`harness/lm.py`）

- `BaseLM`：抽象基类，定义 `complete(messages: list[dict]) -> str`
- `OpenAILM`：调用 OpenAI 兼容接口，接受 `api_key`、`model`（默认 `gpt-4o-mini`）、`base_url`（None 时用官方，传值时支持 DepSeek 等）；捕获 `RateLimitError` 后抛 `LMRateLimitError`，主循环停机并在 UI 显示友好错误
- `MockLM`：接收预设响应列表，按顺序返回；队列耗尽时抛 `RuntimeError("MockLM response queue exhausted")`

### 3.3 代码执行器（`harness/executor.py`）

- **输入**：`Action`（代码字符串）、超时秒数（默认 10）
- **行为**：在 `tempfile.mkdtemp()` 临时目录内用 `subprocess.run` 执行，传入最小 `env（仅 `PATH`/`PYTHONPATH`），stdout/stderr 超过 8KB 截断
- **输出**：`RunResult(stdout, stderr, exit_code, elapsed, timed_out)`
- **注意**：不做护栏检查，调用方必须先过 `guardrail.check()`

### 3.4 失败分类器 + 修复策略路由（`harness/classifier.py`）

**FailureType 枚举**：

| 枚举值 | 触发条件 |
|--------|----------|
| `SYNTAX_ERROR` | `SyntaxError` |
| `NAME_ERROR` | `NameError` / `AttributeError` |
| `TYPE_ERROR` | `TypeError` |
| `IMPORT_ERROR` | `ImportError` / `ModuleNotFoundError` |
| `RUNTIME_ERROR` | 其他运行时异常 |
| `TIMEOUT` | `elapsed >= timeout_limit` |
| `ASSERTION_ERROR` | `AssertionError` |
| `UNKNOWN` | 无法匹配 |

**`classify(result: RunResult) -> FailureInfo`**：纯函数，解析 `stderr` 最后一个 traceback 行，提取异常类名映射到枚举。`FailureInfo` 字段：`type`、`exception_class`、`message`、`line_no`。  
**`get_repair_prompt(info: FailureInfo) -> str`**：每种类型对应固定模板；`IMPORT_ERROR` 模板侧重“识别缺失模块名，提示安装或用标准库替代，不改业务逻辑”；`ASSERTION_ERROR` 模板要求修正逻辑而非删除断言。  
**卡死检测**（在 `agent_loop.py` 实现）：连续 3 轮相同 `FailureType` 时，先尝试切换 `UNKNOWN` 策略重试一次，仍失败则停机返回 `stall`。

### 3.5 治理护栏（`harness/guardrail.py`）

**三态决策**：`ALLOW` / `BLOCK` / `HITL_REQUIRED`

**BLOCK（高危，直接拒绝）**：

- `rm -rf /`、`rm -rf ~` 等递归删除根/家目录
- fork bomb（`:(){ :|:& };:`）
- `dd`、`mkfs` 磁盘覆写调用
- 写入 `/etc/`、`/sys/`、`/proc/`

**HITL_REQUIRED（中危，暂停等待人工审批）**：

- `os.remove`、`shutil.rmtree`（非临时目录）
- `subprocess.run` / `os.system`（任意 shell 执行）
- 写入当前工作目录之外的路径
- `eval()` / `exec()` 调用
- 网络外联实际调用（`socket.connect`、`urllib.request.urlopen`、`requests.get/post`）——匹配实际调用而非 `import`

**`check(action: Action) -> GuardrailDecision`**：纯函数，正则匹配 `action.payload`，先过 BLOCK 规则，再过 HITL 规则，均未命中返回 `ALLOW`。

### 3.6 记忆模块（`harness/memory.py`）

**SQLite 两张表**：

- `sessions`：`id`（UUID PK）、`created_at`、`original_code`、`final_code`（NULL 表示未成功）、`success`（0/1）、`rounds`
- `rounds`：`id`（自增 PK）、`session_id`（FK）、`round_no`、`failure_type`、`error_message`、`action_taken`、`guardrail_decision`

**接口**：

- `start_session(original_code) -> str`
- `append_round(session_id, round: RoundRecord)`
- `finish_session(session_id, final_code, success)`
- `get_recent_sessions(limit=5) -> list[SessionSummary]`

**上下文注入策略**：每次循环开始前取最近 5 次会话的错误类型分布，格式化为一段文字附加在系统提示末尾，不做向量检索。

### 3.7 Streamlit UI（`ui/app.py`）

极简单列布局：代码输入框 → 运行按钮 → 输出流 → HITL 审批区域（条件渲染）→ 历史记录折叠区。  
**HITL 暂停与恢复**：`session_state` 保存完整循环状态（`round_no`、`messagehistory`、`current_code`、`pending_action`、`failure_history`）；检测到 `HITL_REQUIRED` 时主循环函数返回，UI 渲染审批按钮；用户点击批准/拒绝后写入 `session_state`，调用 `st.rerun()` 从保存状态重建上下文继续执行。

---

## 4. 非功能性需求

- **性能**：单次代码执行超时默认 10 秒；LM 调用无硬超时，依赖供应商默认；UI 响应 LM 调用期间显示 spinner
- **安全**：凭据不硬编码、不进 Git；subprocess 沙箱防意外操作，不防对抗性输入（README 明确说明）；`.env` 文件加入 `.gitignore`
- **可用性**：首次运行无 key 时UI 顶部显示 banner 引导配置；HITL 审批区域说明危险操作内容
- **可观测性**：每轮循环在 UI 实时显示轮次、`FailureType`、护栏决策

---

## 5. 系统架构

```text
用户代码输入（Streamlit UI）
        │
        ▼
agent_loop.py
┌────────────────────────────────┐
│ 组装上下文（memory 注入）      │
│            ↓                    │
│ lm.complete()                   │
│            ↓                    │
│ 解析 Action                     │
│            ↓                    │
│ guardrail.check()               │
│  BLOCK ──→ 回灌拒绝原因        │
│  HITL ──→ 返回暂停状态 ──→ UI │
│  ALLOW ──→ executor.run()      │
│            ↓                    │
│ classifier.classify()          │
│            ↓                    │
│ get_repair_prompt()            │
│            ↓                    │
│ memory.append_round()          │
│            ↓                    │
│ 停机判断                        │
└────────────────────────────────┘
        │
        ▼
LoopResult → UI 展示最终结果
```

**外部依赖**：OpenAI 兼容 LM API（DeepSeek / OpenAI）、SQLite（内置）、`keyring`、`streamlit`、`openai` SDK

---

## 6. 数据模型

见 `harness/models.py`：

```python
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class Action:
    type: Literal["run_code", "write_file", "shell", "give_up"]
    payload: str

@dataclass
class RunResult:
    stdout: str
    stderr: str
    exit_code: int
    elapsed: float
    timed_out: bool

@dataclass
class FailureInfo:
    type: FailureType
    exception_class: str
    message: str
    line_no: Optional[int]

@dataclass
class GuardrailDecision:  # 实际是 Enum，此处展示字段语义
    value: Literal["ALLOW", "BLOCK", "HITL_REQUIRED"]

@dataclass
class LoopResult:
    status: Literal["success", "failed", "stall", "hitl_pause", "give_up"]
    final_code: Optional[str]
    rounds: int
    session_id: str
```

---

## 7. 凭据与分发设计

### 凭据

- **威胁模型**：API Key泄露会导致账单损失；主要风险点：硬编码进源码、提交进 Git 历史、写入日志。
- **存储方案**：
  - 本地开发：`keyring` 库写入系统钥匙串（macOS Keychain / Windows Credential Manager / Linux Secret Service）
  - 容器/CI 环境：`keyring` 不可用时 try/except Exception 静默回退到 `OPENAI_API_KEY` 环境变量
  - 两者均无时抛 `RuntimeError("No API key found. Run: python -m harness.cli setup")`
- **录入/更新/清除**：
  - `python -m harness.cli setup`（隐藏输入）
  - `harness.cli key-status`（只显示前4位）
  - `harness.cli key-clear`
- **.env 说明**：明文文件，需加入 `.gitignore`，README 明确说明风险。

### 分发

- **Docker 容器**：
  ```bash
  docker build -t coding-agent-harness .
  echo "OPENAI_API_KEY=sk-..." > .env
  docker run -p 8501:8501 --env-file .env coding-agent-harness
  ```
  容器内统一走环境变量路径（keyring 无宿主钥匙串访问）。

- **Render 部署**：Web Service，连接 GitHub 仓库，`OPENAI_API_KEY` 在 Render Dashboard Environment 面板配置，不进 Git。

---

## 8. 技术选型与理由

| 选项 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.12 | 作业主题是 Python 脚本修复，生态最匹配 |
| UI | Streamlit | 快速构建单页交互，内置 session_state 适合 HITL 暂停 |
| LM 供应商 | DeepSeek（OpenAI 兼容）/ OpenAI | 国内访问无网络问题，接口兼容 OpenAI SDK，可按需切换 |
| 数据库 | SQLite（内置） | 无需部署，单文件持久化足够 |
| 凭据管理 | keyring + env 回退 | 跨平台，无需自行实现加密 |
| 容器 | Docker | 作业要求 + Render 原生支持 |
| CI | GitLab CI（.gitlab-ci.yml） | NJU Git 评分要求 |
| Agent 框架 | 无（自实现主循环） | 作业明确禁止寄生于现成 agent 框架 |

---

## 9. 领域与机制设计（作业 A.5 要求）

### 反馈信号（主要贡献）

- **编码方式**：`classifier.classify()` 是一个纯函数，输入 `RunResult`，输出 `FailureInfo`，通过正则解析 `stderr` 确定性分类，不依赖 LLM 判断。替换为 `MockLM` 后，分类器仍可独立单测。
- **深度**：8 种 `FailureType` 枚举，每种对应独立修复策略模板；卡死检测（连续 3 轮相同类型）作为二级反馈机制，防止无效循环。

### 危险动作护栏

- **编码方式**：`guardrail.check()` 纯函数，正则匹配 `action.payload`，返回三态枚举。不依赖 LLM，可直接用构造的 `Action` 对象单测。
- **HITL 状态机**：`BLOCK`（直接拒绝）和 `HITL_REQUIRED`（暂停等人工）两级，通过 `session_state` 实现暂停恢复。

### 工具/动作

- `run_code`：在沙箱子进程执行 Python 代码
- `write_file`：写入临时目录内的文件
- `shell`：执行 shell 命令（中危，默认触发 HITL）
- `give_up`：LM 显式放弃，主循环停机

### 记忆

- **跨会话持久化**：SQLite 存储会话和轮次记录；上下文注入采用统计摘要（“过去 5 次会话中 NAME_ERROR 出现 N 次”），不做向量检索，保持实现简单且完全自主。

---

## 10. 验收标准

| 功能 | 判定标准 |
|------|----------|
| 主循环 | MockLM 驱动，输入有 SyntaxError 的代码，2 轮内停机且 exit_code==0 |
| 失败分类器 | 8 种 FailureType 各有对应 stderr 样本，classify() 100% 正确分类 |
| 修复策略路由 | 每种 FailureType 调用 get_repair_prompt() 返回字符串各不相同 |
| 卡死检测 | 连续 3 轮相同 FailureType，主循环停机返回 stall |
| 护栏 BLOCK | 高危 payload，guardrail.check() 返回 BLOCK，executor 未被调用 |
| 护栏 HITL | 中危 payload，主循环返回 hitl_pause，session_state 含 pending_action |
| HITL 恢复 | 用户批准后，循环从正确轮次继续，历史消息完整 |
| 记忆写入 | 完整会话后，SQLite sessions 和 rounds 表有对应记录 |
| 记忆注入 | 第二次会话启动时，系统提示包含上次会话错误类型统计摘要 |
| 凭据管理 | keyring 存储后可查看状态（不回显明文）、更新、清除 |
| Docker 分发 | 单条 docker build + docker run --env-file .env 后 UI 可访问 |
| Render 部署 | 公网 URL 可访问，key 在 Dashboard 配置，不在 Git 历史中出现 |

---

## 11. 机制演示（作业 A.6 要求）

`python demo/demo_mechanisms.py`，全程 MockLM，无需网络：

**演示①：护栏拦截 BLOCK**

- MockLM 返回 `Action(type="shell", payload="rm -rf /tmp && rm -rf /")`
- `guardrail.check()` → `BLOCK`
- 输出：`[GUARDRAIL] BLOCKED: matched pattern 'rm -rf /'`
- 断言：executor 未被调用

**演示②：反馈闭环**

- 第 1 轮：MockLM 返回含 `NameError` 的代码
- executor 运行 → `exit_code=1`, `stderr="NameError: name 'x' is not defined"`
- `classifier.classify()` → `FailureType.NAME_ERROR`
- `get_repair_prompt()` → 包含“补充变量定义”的提示
- 第 2 轮：MockLM 返回修复后代码
- executor 运行 → `exit_code=0`
- 主循环停机，`status="success"`

**演示③：卡死检测（主要贡献深度演示）**

- MockLM 连续 3 次返回含相同 `TypeError` 的代码
- 第 3 次相同错误后：`stall_count==3`，主循环停机
- 输出：`[LOOP] Stall detected (TYPE_ERROR ×3), status="stall"`

---

## 12. 风险与未决问题

| 风险 | 缓解措施 |
|------|----------|
| Streamlit HITL 状态恢复复杂，rerun 后上下文丢失 | session_state 保存 5 个完整字段，集成测试覆盖 rerun 路径 |
| Render 免费层冷启动慢（约 30s） | README 说明，提交前手动触发唤醒 |
| subprocess 沙箱不防对抗性输入 | README 安全边界章节明确说明，生产场景应用 gVisor/nsjail |
| keyring 在 Linux headless 环境不可用 | try/except Exception 回退到环境变量 |
| LM 返回非结构化响应 | 解析失败回灌格式错误提示，最多重试 2 次后停机 |
| DeepSeek API 限速/余额不足 | OpenAILM 捕获 RateLimitError 抛 LMRateLimitError，主循环停机，UI 显示友好错误 |