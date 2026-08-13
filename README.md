# Coding Agent Harness

A Streamlit web application where you paste broken Python code and an LLM agent automatically runs, diagnoses, and repairs it — round after round — until it passes or a stop condition triggers.

## Features

- **Auto-repair loop** — up to 8 rounds of run → classify error → prompt LM → fix
- **8 failure types** — SyntaxError, NameError, TypeError, ImportError, AssertionError, RuntimeError, Timeout, Unknown
- **Stall detection** — stops after 3 consecutive identical errors
- **Guardrail system** — BLOCK (high-risk commands rejected silently) / HITL (medium-risk paused for human approval)
- **Session memory** — SQLite stores every round; last 5 sessions injected as context
- **No agent framework** — self-contained main loop, easy to audit

## Quick Start (Docker)

```bash
docker build -t coding-agent-harness .
echo "OPENAI_API_KEY=sk-..." > .env
docker run -p 8501:8501 --env-file .env coding-agent-harness
```

Then open http://localhost:8501.

## Local Development

```bash
pip install -r requirements.txt

# Store API key in system keychain (recommended)
python -m harness.cli setup

# Or use environment variable
export OPENAI_API_KEY=sk-...

# Run the UI
streamlit run ui/app.py

# Run tests
python -m pytest tests/ -v

# Run mechanism demos (no network needed)
python demo/demo_mechanisms.py
```

## API Key Management

```bash
python -m harness.cli setup        # store key (hidden input)
python -m harness.cli key-status   # show first 4 chars only
python -m harness.cli key-clear    # remove from keychain
```

Key lookup order: system keychain → `OPENAI_API_KEY` env var → error.

**Security note:** Never commit `.env` to Git. It is in `.gitignore`. For production, use your platform's secret management (e.g., Render Dashboard environment variables).

## Using DeepSeek or another OpenAI-compatible API

```bash
export OPENAI_API_KEY=sk-...
export OPENAI_BASE_URL=https://njusehub.info/v1
export OPENAI_MODEL=DeepSeek-V3
streamlit run ui/app.py
```

## Live Demo

**Deployed:** https://coding-agentharness.onrender.com

> Note: Free tier sleeps after 15 min inactivity. First request may take ~30s to wake up.

## Render Deployment

1. Push to GitHub/GitLab
2. Create a Render **Web Service**, connect the repo
3. Set **Build Command**: `pip install -r requirements.txt`
4. Set **Start Command**: `streamlit run ui/app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
5. Add `OPENAI_API_KEY` in the Render **Environment** panel — never in the repo

## CI/CD Pipeline

本项目 GitLab CI 流水线包含 `test`、`lint`、`build` 三个阶段。

| 阶段 | Job | 状态 | 说明 |
|------|-----|------|------|
| test | `unit-test` | ✅ pass | `pytest tests/ -v`，87 个测试全部通过（MockLM，无需网络） |
| test | `demo` | ✅ pass | `python demo/demo_mechanisms.py`，3 个机制演示全部通过 |
| lint | `lint` | ✅ pass (allow_failure) | `pyflakes harness/ ui/ demo/` |
| build | `build-docker` | ⚠️ allow_failure | 见下方说明 |

### build 阶段说明

`build-docker` 任务因学校 GitLab Runner 基础设施限制无法完成 Docker 镜像构建，具体原因如下：

**1. Runner 未开启 privileged 模式**

Docker 镜像构建需要 `docker:dind`（Docker-in-Docker）服务，而 dind 要求 Runner 以 `privileged = true` 运行。当前学校 Runner（`linux-docker-1`）未开启此配置，`dockerd` 无法挂载文件系统，健康检查超时：

```
mount: permission denied (are you root?)
AppArmor detection and --privileged mode might break.
```

学生仅有仓库管理权限，无法修改 Runner 的 `config.toml` 配置。

**2. 网络访问受限**

Runner 网络仅可访问 Docker Hub（`docker.io`），无法访问 `gcr.io`（Kaniko 镜像源）及国内镜像代理（`gcr.chenby.cn`），导致无 privileged 依赖的 Kaniko 构建方案同样不可用。

**3. 已尝试的替代方案**

| 方案 | 说明 | 结果 |
|------|------|------|
| `docker:dind` + 禁用 TLS | 标准 Docker 构建 | 失败（需 privileged） |
| Kaniko（`gcr.chenby.cn`） | 无 privileged 构建 | 失败（镜像不可达） |
| Python 模拟构建 | 用 `python:3.12-slim` 验证 Dockerfile 步骤 | 通过（当前方案） |

**4. Dockerfile 本身有效**

Dockerfile 语法正确、逻辑完整，在本地 Docker 环境中可正常构建。CI 中的构建失败均为 Runner 环境问题，非项目代码问题。该任务已设置 `allow_failure: true`，流水线整体状态为 **passed**。

## Architecture

```
ui/app.py  (Streamlit)
    │
    ▼
harness/agent_loop.py  ← main loop
    ├── harness/lm.py          (BaseLM / OpenAILM / MockLM)
    ├── harness/executor.py    (subprocess sandbox)
    ├── harness/classifier.py  (stderr → FailureType)
    ├── harness/guardrail.py   (BLOCK / HITL / ALLOW)
    └── harness/memory.py      (SQLite sessions + rounds)
```

## Guardrail Reference

| Decision | Examples |
|---|---|
| BLOCK | `rm -rf /`, fork bomb, `dd`, `mkfs`, writes to `/etc/` `/sys/` `/proc/` |
| HITL | `os.remove`, `shutil.rmtree`, `subprocess.run`, `eval`, `exec`, network calls |
| ALLOW | Everything else |

## Security Boundaries

- The subprocess sandbox prevents accidental operations but **is not hardened against adversarial input**. Do not expose this service publicly without additional isolation (gVisor, nsjail, etc.).
- API keys are never logged or echoed. The CLI shows only the first 4 characters.

## Project Structure

```
harness/       core modules (models, lm, executor, classifier, guardrail, memory, agent_loop, cli)
ui/            Streamlit app
demo/          MockLM demos (no network)
tests/         pytest test suite
Dockerfile
.gitlab-ci.yml
requirements.txt
```
