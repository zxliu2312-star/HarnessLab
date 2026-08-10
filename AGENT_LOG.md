# AGENT_LOG.md

记录 Coding Agent Harness 项目开发关键节点，按时间顺序排列。

---

## 2026-08-08 | 项目启动 · 选题与技术决策

**触发技能：** brainstorming

**关键决策记录：**

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 项目类型 | Coding Agent Harness (A类) | 完全符合课程要求，机制最清晰 |
| 选题 | Python 脚本自动修复 Agent | 反馈信号客观确定，mock 测试好写 |
| 主要贡献维度 | 反馈闭环（失败分类器 + 修复策略路由） | 最贴近 coding agent 本质，单测最好验证 |
| LM 供应商 | DepSeek（OpenAI 兼容接口） | 国内访问稳定，接口兼容，成本低 |
| 护栏方案 | 静态黑名单 + HITL 暂停（B 方案） | 有两级状态机，比纯黑名单有工程深度 |
| UI 方案 | Streamlit 极简单列（C 方案） | 实现最快，HITL 按钮最自然 |
| 分发 | Docker 容器 | 最简单，Render 原生支持 |
| 凭据 | keyring + .env 回退 | 跨平台，几行代码搞定 |

**人工干预：**
- 将 brainstorming 提出的 `strategy.py` 合并进 `classifier.py`，减少模块数量
- 去掉 `guardrail_rules.yaml`，护栏规则硬编码，与 B 方案保持一致
- 网络外联规则从 BLOCK 降为 HITL_REQUIRED，只匹配实际连接调用
- 补充 `IMPORT_ERROR` 枚举类型处理 ModuleNotFoundError
- MockLM 队列耗尽改为抛明确 RuntimeError 而非 IndexError
- 补充 Streamlit HITL 恢复机制说明（session_state 需保存完整循环状态）
- keyring 在容器环境加 try/except 保护
- CI 配置文件改为 .gitlab-ci.yml（NJU Git 评分要求）
- 演示③ MockLM 响应次数修正为 3 次（与 stall_count 判断条件对齐）
- 风险表补充 DepSeek API 限速/余额不足的缓解措施

**产出：** SPEC.md（12节，覆盖所有课程要求章节）

---

## 2026-08-09 | PLAN生成

**触发技能：** writing-plans

**关键内容：**
- 共 10 个 Task
- 每个 Task 包含完整测试代码、实现代码、验证命令
- 全程使用 MockLM，无需网络即可运行所有单元测试

**产出：** PLAN.md（750行）

---

<!-- 以下为实现阶段模板，每完成一个 Task 填写一条 -->

## 2026-08-09 | Task 1: 数据模型

**触发技能：** subagent-driven-development / executing-plans

**Subagent：** [记录使用的模型]

**Commit hash：** 78bd173

**测试结果：** pytest tests/test_models.py — X tests PASSED

**人工干预：** [如有修改，记录修改了什么、为什么]

**教训：** [如有踩坑，记录]

---

## 2026-08-09 | Task 2: LM 抽象层

**Commit hash：** ad86594

**测试结果：** pytest tests/test_lm.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 3: 代码执行器

**Commit hash：** 44c69e9

**测试结果：** pytest tests/test_executor.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 4: 失败分类器

**Commit hash：** a104d87

**测试结果：** pytest tests/test_classifier.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 5: 治理护栏

**Commit hash：** db61a00

**测试结果：** pytest tests/test_guardrail.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 6: 记忆模块

**Commit hash：** e12d9cb

**测试结果：** pytest tests/test_memory.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 7: Agent 主循环

**Commit hash：** 8e04572

**测试结果：** pytest tests/test_agent_loop.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 8: Streamlit UI + HITL

**Commit hash：** bc22aa3

**测试结果：** pytest tests/test_ui_hitl.py — X tests PASSED

**人工干预：** [如有]

---

## 2026-08-09 | Task 9: CLI凭据管理

**Commit hash：** 5b6f6e6

**测试结果：** [填写]

**人工干预：** [如有]

---

## 2026-08-09 | Task 10: Demo 脚本

**Commit hash：** 9833fd6

**验证：** python demo/demo_mechanisms.py 全部通过

---

## 2026-08-09 | Task 11: Docker + CI + 部署

**Commit hash：** 802d011（文档）→ 946138b → f9adb56（部署修复）

**验证：**
- docker build 成功
- .gitlab-ci.yml unit-test job PASSED
- Render 公网 URL 可访问：https://coding-agentharness.onrender.com

---