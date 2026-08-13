LLM: claude-sonnet-4-6(使用的自己的账户)

lzx:
@z:\HarnessLab\superpowers\superpowers\skills\brainstorming\SKILL.md

我想做一个 Python 脚本自动修复 Coding Agent Harness。用户输入一段有 bug 的 Python 代码，agent 自动运行它、捕获报错、修复、循环直到通过。这是一门 AI4SE 课程的期末作业，需要自己实现 agent 主循环、LM 抽象层、反馈闭环（运行+解析 stderr）、治理护栏（拦截危险操作）、记忆模块，并提供 Streamlit WebUI，用 Docker 分发，部署到 Render。

superpowers:
需求文件读完了，背景很清楚。

第一个问题：作业要求你选一个维度"做深"作为主要贡献。你倾向于哪个方向？

A. 治理护栏：设计一套确定性的危险动作拦截系统，包含 HITL（人工审批）状态机、沙箱围栏、多级规则引擎——代码量集中、单测最好写、最能体现"编码了机制"
B. 反馈闭环：多轮自我修正的核心引擎，包含失败分类器（语法错/运行时错/逻辑错）、修复策略路由、回归检测——最贴近"coding agent"的本质
C. 记忆模块：自己实现向量检索 + 会话摘要 + 跨会话持久化，不用任何框架的 memory——工程量最大，但差异化最强

lzx:
反馈闭环作为主要贡献，治理护栏作为基础机制都实现，但不做深。

superpowers:
好，反馈闭环为主。下一个问题：

LM 供应商你用哪个？这决定抽象层的设计和凭据管理方案。

A. OpenAI / DepSeek（OpenAI 兼容接口） — API 格式完全一致，抽象层最薄，国内访问 DepSeek 没有网络问题
B. Anthropic Claude — 接口格式略有差异，需要单独适配，但模型质量高
C. 两者都支持，运行时可切换 — 抽象层稍复杂，但满足"可注入 mock"要求更优雅，也更能体现 LM 抽象层的设计价值

lzx:
A

superpowers:
好，OpenAI 兼容接口。下一个问题：

反馈闭环的"深度"你想做到哪一层？

A. 基础层：运行代码 → 捕获 stderr → 把错误文本回灌给 LLM → 循环。够用，但闭环逻辑基本全在提示词里，评分时"机制是否编码"存疑
B. 中层（推荐）：在 A 基础上加一个确定性失败分类器——代码解析 stderr，判断是 SyntaxError / RuntimeError / TimeoutError / AssertionError 等类型，不同类型走不同修复策略路由；分类器本身可以用 mock LM 单独测试
C. 深层：在 B 基础上再加回归检测——修复后自动对比本次 fix 是否引入了新的失败点，并记录每轮的错误类型分布作为会话记忆

lzx:
B

superpowers:
好，失败分类器 + 策略路由。下一个问题：

治理护栏的触发方式你倾向哪种？这影响 harness 主循环的结构。

A. 静态黑名单：维护一个危险命令/模式列表（rm -rf、DROP TABLE、写 /etc 等），agent 要执行动作前用正则/字符串匹配拦截，拦截后直接拒绝并告知 LLM
B. 静态黑名单 + HITL 暂停：在 A 基础上区分"直接拒绝"和"暂停等待人工确认"两种处理——高危直接拒，中危暂停让用户在 UI 里点"批准/拒绝"，批准后继续循环
C. 可配置规则引擎：护栏规则从配置文件读取（YAML/JSON），支持运行时热更新，用户可自定义哪些操作需要 HITL、哪些直接拒绝

lzx:
B

superpowers:
好，HITL 暂停。下一个问题：

记忆模块的范围你想做到哪里？作业要求"基础都要有"，但不是重点。

A. 最小实现：只做会话内记忆——把每轮的错误类型、修复动作、是否成功追加到一个列表，作为上下文窗口的一部分传给 LLM，会话结束后不持久化
B. 跨会话持久化：在 A 基础上把会话历史写到本地 SQLite，下次启动时可以加载最近 N 条历史作为参考上下文（"上次这个错误这么修好的"）
C. B + 项目级知识库：用户可以向 agent 注入项目约定（如"这个项目不用 f-string"），持久化存储，每次修复前自动注入到系统提示

lzx:
B

superpowers:
好，SQLite 跨会话持久化。最后一个问题：

Streamlit UI 的交互模式你想要哪种？这直接影响 HITL 暂停的实现方式。

A. 单页流式：左侧输入代码，右侧实时滚动显示每轮循环的运行结果、错误分类、LM 修复动作；HITL 暂停时在右侧弹出"批准/拒绝"按钮，用户点击后循环继续
B. 多 tab 分栏：Tab1 是主交互（输入+运行），Tab2 是会话历史（从 SQLite 加载），Tab3 是护栏审计日志（记录每次拦截事件）；HITL 在 Tab1 内处理
C. 极简单列：所有内容垂直排列，不分 tab，代码输入框 → 运行按钮 → 输出流 → HITL 审批区域 → 历史记录折叠区；最容易实现，视觉最清晰

lzx:
C

superpowers:
好，信息收集完毕。现在提出三种整体架构方案供你选择。

三种方案
方案一：单进程同步循环（推荐）
主循环、分类器、护栏、记忆全在一个 Python 进程里，Streamlit 直接调用。 st.session_state 管理 HITL 暂停状态——循环检测到高危动作时把状态写入 session_state，UI 重渲染显示审批按钮，用户点击后循环继续。

优点：结构最简单，主循环是纯 Python 函数，最容易用 mock LM 写单测；HITL 不需要线程/队列，靠 Streamlit 的 rerun 机制天然实现。 缺点：长时间运行（LM 调用 + 代码执行）会阻塞 Streamlit 主线程，输出无法真正流式——需要用 st.spinner 占位，而非逐行实时刷新。

方案二：主循环跑在后台线程，UI 轮询
主循环在 threading.Thread 里运行，通过 queue.Queue 向 Streamlit 推事件（每轮结果、HITL 请求）；UI 用 st.rerun() 定时刷新消费队列。

优点：UI 不阻塞，可以逐条显示每轮进度；更接近真实 agent 的异步感。 缺点：线程安全复杂，session_state 跨线程访问有坑；HITL 需要额外的 Event 同步原语；单测需要 mock 队列，复杂度上升。

方案三：FastAPI 后端 + Streamlit 前端
主循环跑在 FastAPI 里，Streamlit 通过 HTTP 轮询状态。两者分离，Docker Compose 编排。

优点：后端完全独立，单测最干净；理论上可以接多个前端。 缺点：对这个规模的项目过度设计；Docker Compose 在 Render 免费层部署复杂；HITL 需要 REST endpoint +轮询，工作量翻倍；和作业"用一个 Python 脚本"的初始描述偏差最大。

我推荐方案一，理由：

作业评分核心是"机制是否编码"和"mock LM 单测"，方案一的主循环是一个纯函数，最容易隔离测试。HITL 暂停用 session_state 实现是 Streamlit 的惯用模式，不引入并发复杂度。Render 部署只需一个容器，最省事。

你选哪个方案？

lzx:
方案一

superpowers:
好，方案一。现在逐节呈现设计，每节确认后再继续。

设计第一节：系统架构与模块划分
src/
├── harness/
│   ├── agent_loop.py       # 主循环：组织上下文 → 调用 LM → 解析动作 → 分发执行 → 回灌 → 停机判断
│   ├── lm.py               # LM 抽象层：BaseLM 接口 + OpenAILM 实现 + MockLM（离线测试用）
│   ├── executor.py         # 工具执行：在子进程沙箱里运行用户代码，捕获 stdout/stderr，超时控制
│   ├── classifier.py       # 失败分类器：解析 stderr → 返回 FailureType 枚举 + 结构化错误信息
│   ├── strategy.py         # 修复策略路由：根据 FailureType 选择对应的修复提示模板
│   ├── guardrail.py        # 治理护栏：检测危险动作 → BLOCK / HITL_REQUIRED / ALLOW三态
│   ├── memory.py           # 记忆模块：SQLite 读写，会话历史持久化，上下文注入
│   └── models.py           # 数据模型：Action、RunResult、FailureInfo、GuardrailDecision、Session
├── ui/
│   └── app.py              # Streamlit 单页 UI，管理 HITL 暂停状态
├── tests/
│   ├── test_classifier.py
│   ├── test_guardrail.py
│   ├── test_strategy.py
│   ├── test_agent_loop.py  # 用 MockLM 驱动完整主循环
│   └── test_memory.py
├── config/
│   └── guardrail_rules.yaml  # 危险模式配置（可选，基础实现可硬编码）
Dockerfile
docker-compose.yml          # 本地开发用，Render 只用 Dockerfile
requirements.txt
数据流（一轮循环）：

用户代码输入
    → agent_loop: 组装 [系统提示 + 记忆注入 + 历史轮次 + 当前代码]
    → lm.complete(): 返回 LM 决策（动作类型 + 修复后代码 或 终止信号）
    → guardrail.check(): ALLOW → executor.run() / HITL_REQUIRED → 暂停 / BLOCK →拒绝
    → executor.run(): 子进程执行，返回 RunResult(stdout, stderr, exit_code, elapsed)
    → classifier.classify(): RunResult → FailureInfo(type, message, line_no)
    → strategy.get_prompt(): FailureInfo → 针对性修复提示
    → memory.append(): 本轮结果写入 SQLite
    → 回到顶部，继续下一轮（或 exit_code==0 时停机）
停机条件（任一满足）：

exit_code == 0（代码通过）
达到最大轮次上限（默认 8，可配置）
连续 3 轮产生相同错误类型（卡死检测，避免无效循环）
LM 返回显式放弃信号
这节设计是否符合你的预期？有没有哪个模块边界需要调整？

lzx:
整体架构认可。两点调整：1. strategy.py 合并进 classifier.py，减少模块数量；2. 去掉 guardrail_rules.yaml，护栏规则硬编码，与之前选的 B 方案保持一致。其余全部确认，进入下一节。

superpowers:
收到，合并后结构：

classifier.py = 失败分类 + 策略路由（classify() 返回 FailureInfo，get_repair_prompt() 根据 FailureType 返回提示模板）
guardrail.py = 硬编码规则，无外部配置文件
设计第二节：反馈闭环（主要贡献）
这是评分重心，需要把机制说清楚到可以直接写测试的粒度。

FailureType 枚举
class FailureType(Enum):
    SYNTAX_ERROR      # SyntaxError，代码解析阶段失败
    NAME_ERROR        # NameError / AttributeError，未定义引用
    TYPE_ERROR        # TypeError，类型不匹配
    RUNTIME_ERROR     # 其他运行时异常（ValueError、ZeroDivisionError 等）
    TIMEOUT           # 超过执行时限
    ASSERTION_ERROR   # AssertionError，逻辑验证失败
    UNKNOWN           # 无法归类
classifier.classify(result: RunResult) -> FailureInfo
纯函数，输入 RunResult，输出 FailureInfo。判断逻辑：

exit_code == 0 → 不调用 classify，主循环直接停机
elapsed >= timeout_limit → TIMEOUT
解析 stderr 最后一个 traceback 行，提取异常类名，按上表枚举映射
无法匹配 → UNKNOWN
FailureInfo 字段：type: FailureType、exception_class: str、message: str、line_no: int | None

classifier.get_repair_prompt(info: FailureInfo) -> str
每种 FailureType 对应一个修复提示模板，差异点：

| FailureType | 提示侧重 | |---| | SYNTAX_ERROR | 指出行号，要求只修语法，不改逻辑 | | NAME_ERROR | 列出未定义名称，要求补充定义或修正拼写 | | TYPE_ERROR | 说明类型冲突位置，要求加类型转换或修正调用 | | RUNTIME_ERROR | 附上完整 traceback，要求防御性修复 | | TIMEOUT | 要求优化算法复杂度或加提前终止 | | ASSERTION_ERROR | 说明断言位置，要求修正逻辑而非删除断言 | | UNKNOWN | 附上完整 stderr，要求通用修复 |

卡死检测（在 agent_loop.py 里实现）
# 连续相同 FailureType 计数
if last_failure_type == current_failure_type:
    stall_count += 1
else:
    stall_count = 0
if stall_count >= 3:
    # 切换到 UNKNOWN 策略重试一次，仍失败则停机
单测覆盖点（mock LM 可独立验证）
classify() 对每种 FailureType 的 stderr 样本都能正确分类
get_repair_prompt() 对不同类型返回不同模板（字符串不同）
主循环注入 mock LM，第一轮返回有 SyntaxError 的代码，第二轮返回修复代码 → 验证循环在第二轮停机
主循环注入连续返回相同错误的 mock LM → 验证卡死检测在第 3 次相同错误后停机
这节是否符合预期？特别是 FailureType 枚举够用吗，有需要增删的类型吗？

lzx:
这节确认。补充一个 IMPORT_ERROR 类型处理 ImportError / ModuleNotFoundError，修复策略是提示缺少依赖而非修改代码逻辑。其余全部认可，进入下一节。

superpowers:
收到，IMPORT_ERROR 加入枚举，修复策略模板侧重"识别缺失模块名，提示用户安装或用标准库替代，不改业务逻辑"。

设计第三节：治理护栏
三态决策
class GuardrailDecision(Enum):
    ALLOW           # 放行
    BLOCK           # 直接拒绝，告知 LLM 原因，不执行
    HITL_REQUIRED   # 暂停，等待人工审批
硬编码规则（两级）
直接 BLOCK（高危，无需人工确认）：

模式	理由
rm -rf /、rm -rf ~ 等递归删除根/家目录
不可逆破坏宿主机
:(){ :|:& };: fork bomb
资源耗尽攻击
os.system / subprocess调用 dd、mkfs
磁盘覆写
写入 /etc/、/sys/、/proc/
系统配置篡改
网络外联（socket.connect、urllib、requests 调外部 IP）
数据外泄风险
HITL_REQUIRED（中危，暂停等待审批）：

模式	理由
os.remove、shutil.rmtree（非临时目录）
文件删除需确认
subprocess.run / os.system（非白名单命令）
任意 shell 执行
写入当前工作目录之外的路径
越界写入
eval()、exec() 调用
动态代码执行
guardrail.check(action: Action) -> GuardrailDecision
Action 有两个字段：type: Literal["run_code", "write_file", "shell"] 和 payload: str（代码内容或命令字符串）。

检查逻辑：正则匹配 payload，先过 BLOCK 规则，再过 HITL 规则，均未命中则 ALLOW。纯函数，无副作用。

HITL 在Streamlit 里的实现
主循环遇到 HITL_REQUIRED
    → 把 pending_action 写入 st.session_state
    → 主循环函数返回（不继续）
    → Streamlit 重渲染，显示审批区域：
        "Agent 请求执行：<动作描述>"
        [批准] [拒绝]
    → 用户点击
        → 批准：session_state 写入 approved=True，st.rerun() 恢复循环
        → 拒绝：把拒绝原因回灌给 LLM，继续循环
单测覆盖点
传入高危 payload →返回 BLOCK
传入中危 payload → 返回 HITL_REQUIRED
传入普通代码 → 返回 ALLOW
主循环 mock 测试：注入触发 HITL 的 LM 响应 → 验证循环暂停（返回 HITL_REQUIRED 状态而非继续执行）
这节是否符合预期？HITL 审批流程和护栏规则分级有没有需要调整的地方？

lzx:
这节基本确认。两点调整：1. 网络外联规则从 BLOCK 降为 HITL_REQUIRED，只匹配实际连接调用而非 import；2. 请在 SPEC 里补充说明 Streamlit HITL 恢复机制需要在 session_state 中保存完整循环状态（轮次、历史消息、待执行动作），st.rerun() 后从 session_state 重建上下文继续执行。其余确认，进入下一节。

superpowers:
收到。网络外联降为 HITL，匹配 socket.connect、urllib.request.urlopen、requests.get/post 等实际调用而非 import。session_state 需持久化：round_no、message_history、current_code、pending_action、failure_history，rerun 后从这五个字段完整重建循环上下文。

设计第四节：记忆模块 + LM 抽象层 + 凭据管理
记忆模块（SQLite）
两张表：

sessions | 字段 | 类型 | 说明 | |---|---| | id | TEXT PK | UUID | | created_at | INTEGER | Unix 时间戳 | | original_code | TEXT | 用户原始输入 | | final_code | TEXT | 最终修复结果（NULL 表示未成功） | | success | INTEGER | 0/1 | | rounds | INTEGER | 总轮次 |

rounds

字段	类型	说明
id
INTEGER PK
自增
session_id
TEXT FK
关联 sessions
round_no
INTEGER
轮次编号
failure_type
TEXT
FailureType 枚举名，NULL 表示成功轮
error_message
TEXT
stderr 摘要
action_taken
TEXT
LM 返回的动作描述
guardrail_decision
TEXT
ALLOW/BLOCK/HITL_REQUIRED
memory.py 接口：

def start_session(original_code: str) -> str          # 返回 session_id
def append_round(session_id: str, round: RoundRecord)  # 写入一轮结果
def finish_session(session_id: str, final_code: str, success: bool)
def get_recent_sessions(limit: int = 5) -> list[SessionSummary]  # 注入上下文用
上下文注入策略：每次循环开始前，get_recent_sessions(5) 取最近 5 次会话的 failure_type 分布和最终是否成功，格式化成一段文字附加在系统提示末尾（"过去 5 次会话中 SYNTAX_ERROR 出现 8 次，TIMEOUT 出现 2 次"）。不做向量检索，保持简单。

LM 抽象层
class BaseLM(ABC):
    @abstractmethod
    def complete(self, messages: list[dict]) -> str: ...
class OpenAILM(BaseLM):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini", base_url: str | None = None):
        # base_url 为 None 时用 OpenAI 官方，传入时支持 DepSeek 等兼容接口
        ...
    def complete(self, messages: list[dict]) -> str: ...
class MockLM(BaseLM):
    def __init__(self, responses: list[str]):
        # 按顺序返回预设响应，用于离线测试
        self._queue = list(responses)
    def complete(self, messages: list[dict]) -> str:
        return self._queue.pop(0)
agent_loop.py 的 AgentLoop.__init__ 接收 lm: BaseLM，测试时注入 MockLM，生产时注入 OpenAILM。

凭据管理
存储方案：keyring 库（跨平台，macOS Keychain / Windows Credential Manager / Linux Secret Service 自动适配）。服务名 coding-agentharness，键名 openai_api_key。

首次运行引导（CLI python -m harness.cli setup）：

未检测到 API Key。
请输入 OpenAI/兼容接口 API Key（输入不回显）：****
Base URL（留空使用 OpenAI 官方）：
Key 已安全存储到系统钥匙串。
Streamlit 启动时：keyring.get_password(...) 取 key，取不到则在 UI顶部显示 banner 引导用户先运行 setup。

.env 回退（容器/CI 环境）：keyring 取不到时检查 OPENAI_API_KEY 环境变量，.env 文件加 .gitignore，README 明确说明这是明文回退方案。

这节是否符合预期？特别是记忆注入策略（统计摘要而非原始历史）和凭据的 keyring + env 双轨方案，有需要调整的吗？

lzx:
这节确认。补充一点：MockLM 队列耗尽时应抛出明确的 RuntimeError（"response queue exhausted"），而不是让 IndexError 静默传播，方便测试时快速定位循环轮次异常。其余全部认可，进入下一节。

superpowers:
收到，MockLM.complete() 在队列空时抛 RuntimeError("MockLM response queue exhausted")。

设计第五节：executor + 分发 + 部署
executor.py（代码执行沙箱）
用 subprocess.run 在独立子进程执行用户代码，不用 Docker沙箱（Render 免费层不支持嵌套容器）。隔离手段：

措施	实现
超时控制
subprocess.run(timeout=10)，可配置，超时抛 TimeoutExpired → FailureType.TIMEOUT
工作目录隔离
每次执行在 tempfile.mkdtemp() 创建的临时目录，执行后清理
环境变量清洁
传入最小 env（只含 PATH 和 PYTHONPATH），不继承父进程环境
输出截断
stdout/stderr 超过 8KB 时截断，避免 LM 上下文爆炸
RunResult 字段：stdout: str、stderr: str、exit_code: int、elapsed: float、timed_out: bool

护栏前置：executor.run() 内部不做护栏检查，调用方（agent_loop）必须先过 guardrail.check()。这保证护栏逻辑与执行逻辑解耦，各自可独立测试。

分发：Docker
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8501
CMD ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0"]
用户拿到镜像后的启动流程：

# 构建
docker build -t coding-agent-harness .
# 首次配置 key（写入容器外的 .env，挂载进容器）
echo "OPENAI_API_KEY=sk-..." > .env
# 运行
docker run -p 8501:8501 --env-file .env coding-agent-harness
容器内 keyring 无法访问宿主系统钥匙串，统一走 OPENAI_API_KEY 环境变量回退路径。README 明确说明 .env 是明文，须加入 .gitignore。

部署：Render
服务类型：Web Service，连接 GitHub 仓库，Render 自动检测 Dockerfile 构建
环境变量在 Render Dashboard 的 Environment 面板配置 OPENAI_API_KEY，不进 Git
免费层限制：实例闲置 15 分钟后休眠，冷启动约 30 秒；每月 750 小时免费额度
render.yaml（可选，基础设施即代码）：
services:
  - type: web
    name: coding-agent-harness
    runtime: docker
    envVars:
      - key: OPENAI_API_KEY
        sync: false   # 标记为手动填写，不从 Git 同步
CI（GitHub Actions）
jobs:
  unit-test:          # 作业要求此 job 必须存在且名称固定
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -r requirements.txt
      - run: pytest tests/ -v
        # 全程使用 MockLM，无需网络，无需真实 key
  build-docker:
    needs: unit-test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t coding-agent-harness .
这节是否符合预期？特别是 executor 的沙箱边界（不用嵌套容器）和 Render 部署方案有没有问题？

lzx:
这节确认。两点补充：1. CI 只需要提供 .gitlab-ci.yml（NJU Git 评分用，必须有 unit-test job），两者格式不同；2. keyring 在容器环境可能抛异常，代码里需要 try/except 包裹后再回退到环境变量。其余全部认可，进入下一节。

superpowers:
收到。CI 只写 .gitlab-ci.yml，不写 GitHub Actions。keyring.get_password() 用 try/except Exception 包裹，捕获 keyring.errors.KeyringError 及任何后端不可用异常，静默回退到 os.environ.get("OPENAI_API_KEY")，两者均无时启动时抛明确的 RuntimeError("No API key found...")。

设计第六节：验收标准 + 机制演示 + 风险
验收标准（每项"完成"的客观判定）
功能	判定标准
主循环
MockLM 驱动下，输入有 SyntaxError 的代码，2 轮内停机且 exit_code==0
失败分类器
7 种 FailureType 各有对应 stderr 样本，classify() 100% 正确分类
修复策略路由
每种 FailureType 调用 get_repair_prompt() 返回字符串各不相同
卡死检测
连续 3 轮相同 FailureType，主循环停机，返回 stall 状态
护栏 BLOCK
传入高危 payload，guardrail.check() 返回 BLOCK，executor 未被调用
护栏 HITL
传入中危 payload，主循环返回暂停状态，session_state 含 pending_action
HITL 恢复
用户点击批准后，循环从正确轮次继续，历史消息完整
记忆写入
一次完整会话后，SQLite 中 sessions 和 rounds 表有对应记录
记忆注入
第二次会话启动时，系统提示包含上次会话的错误类型统计摘要
凭据管理
keyring 存储后可查看状态（不回显明文）、更新、清除
Docker 分发
单条 docker build + docker run --env-file .env 后 UI 可访问
Render 部署
公网 URL 可访问，key 在 Dashboard 配置，不在 Git 历史中出现
机制演示（作业 A.6 要求，可重复运行脚本）
python demo/demo_mechanisms.py，无需网络，无需真实 LM，全程 MockLM：

演示①：护栏拦截

MockLM 返回动作：shell("rm -rf /tmp/test && rm -rf /")
guardrail.check() → BLOCK
输出：[GUARDRAIL] BLOCKED: matched pattern'rm -rf /'
executor 未调用（断言验证）
演示②：反馈闭环

第 1 轮：MockLM 返回含NameError 的代码
executor 运行 → exit_code=1, stderr="NameError: name 'x' is not defined"
classifier.classify() → FailureType.NAME_ERROR
get_repair_prompt() → 包含"补充变量定义"的提示
第 2 轮：MockLM 返回修复后代码
executor 运行 → exit_code=0
主循环停机，输出修复结果
演示③：卡死检测（主要贡献深度演示）

MockLM 连续 4 次返回含相同 TypeError 的代码
第 3 次相同错误后：stall_count==3，主循环停机
输出：[LOOP] Stall detected (TYPE_ERROR x3), aborting
风险与未决问题
| 风险 | 缓解措施 | |---| | Streamlit HITL 状态恢复复杂，rerun 后上下文丢失 | session_state 保存完整循环状态（第三节已设计），集成测试覆盖 rerun 路径 | | Render 免费层冷启动慢，评审时可能看到 30s 空白 | README 说明冷启动情况，提交前手动触发一次唤醒 | | subprocess 沙箱不完整，恶意代码仍可访问文件系统 | README 安全边界章节明确说明：本项目沙箱仅防止意外，不防对抗性输入；生产场景应用 gVisor/nsjail | | keyring 在 Linux headless 环境（Render）不可用 | try/except 回退到环境变量（第五节已设计） | | LM 返回非结构化响应，动作解析失败 | 解析失败时回灌错误信息要求 LM 重新格式化，最多重试 2 次后停机 |

整体设计到这里已完整。是否认可这节内容？确认后我立即写入 SPEC.md 并提交，然后请你审阅文件。

lzx:
这节基本确认。两点修正：1. 演示③的 MockLM 响应次数改为 3 次（连续 3 轮相同 TypeError 即触发停机），与 agent_loop.py 判断条件严格对齐；2. 风险表补充一条"DeepSeek API 限速/余额不足"，缓解措施是 OpenAILM 捕获 RateLimitError 后向上抛出明确异常，主循环停机并在 UI 显示友好错误。确认后写入 SPEC.md。

---

冷启动验证：
# 1. GPT系列
GPT-5.6 Luna：
已严格按照你提供的 SPEC + PLAN 实现 Task 1，没有引入额外字段、行为或依赖。数据模型的接口与 PLAN 中的定义一致；SPEC 也明确了这些模型通过 dataclass 在模块间通信。

已创建：

harness/__init__.py
harness/models.py
tests/test_models.py

其中 FailureType 严格采用 SPEC/PLAN 中规定的 8 个枚举值。

测试结果

tests/test_models.py 共 5 个测试，全部通过：

tests/test_models.py::test_action_fields PASSED
tests/test_models.py::test_run_result_fields PASSED
tests/test_models.py::test_failure_type_enum PASSED
tests/test_models.py::test_loop_result_fields PASSED
tests/test_models.py::test_failure_info_line_no_optional PASSED

5 passed

测试时需要使用 PYTHONPATH=.；直接运行 pytest 时当前环境的 pytest 没有把项目根目录加入模块搜索路径，这是测试环境行为，不是 Task 1 代码问题。

文件已放在：

/mnt/data/coding-agent-harness/

我没有实现 Task 2 及后续任务，也没有自行扩展 Task 1 的模型行为。

lzx人工行为: 把给我的压缩包解压到Z:\HarnessLab\cold_start_verify并把文件夹重命名为task1-harness-GPT-5.6 Luna

# 2. Gemini系列
Gemini 3.6 Flash：
harness/__init__.py
harness/models.py
Python
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class FailureType(Enum):
    SYNTAX_ERROR = "SYNTAX_ERROR"
    NAME_ERROR = "NAME_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"
    ASSERTION_ERROR = "ASSERTION_ERROR"
    UNKNOWN = "UNKNOWN"


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
    line_no: int | None


@dataclass
class LoopResult:
    status: Literal["success", "failed", "stall", "hitl_pause", "give_up"]
    final_code: str | None
    rounds: int
    session_id: str


@dataclass
class RoundRecord:
    round_no: int
    failure_type: str
    error_message: str
    action_taken: str
    guardrail_decision: str


@dataclass
class SessionSummary:
    session_id: str
    created_at: str
    success: bool
    rounds: int
    failure_types: list[str]
tests/test_models.py
Python
from harness.models import (
    Action,
    RunResult,
    FailureInfo,
    FailureType,
    LoopResult,
    RoundRecord,
    SessionSummary,
)


def test_action_fields():
    a = Action(type="run_code", payload="print(1)")
    assert a.type == "run_code"
    assert a.payload == "print(1)"


def test_run_result_fields():
    r = RunResult(stdout="hi", stderr="", exit_code=0, elapsed=0.1, timed_out=False)
    assert r.exit_code == 0
    assert not r.timed_out


def test_failure_type_enum():
    assert FailureType.SYNTAX_ERROR.value == "SYNTAX_ERROR"
    assert len(list(FailureType)) == 8


def test_loop_result_fields():
    lr = LoopResult(status="success", final_code="print(1)", rounds=2, session_id="abc")
    assert lr.status == "success"
    assert lr.rounds == 2


def test_failure_info_line_no_optional():
    fi = FailureInfo(type=FailureType.UNKNOWN, exception_class="", message="", line_no=None)
    assert fi.line_no is None


def test_round_record_fields():
    rr = RoundRecord(
        round_no=1,
        failure_type="SYNTAX_ERROR",
        error_message="invalid syntax",
        action_taken="run_code",
        guardrail_decision="ALLOW",
    )
    assert rr.round_no == 1
    assert rr.guardrail_decision == "ALLOW"


def test_session_summary_fields():
    ss = SessionSummary(
        session_id="sess-123",
        created_at="2026-08-10T00:00:00",
        success=True,
        rounds=3,
        failure_types=["SYNTAX_ERROR", "NAME_ERROR"],
    )
    assert ss.session_id == "sess-123"
    assert ss.success is True
    assert len(ss.failure_types) == 2

# 3. 豆包
豆包 2.0 专家模型：
Task 1 实现：数据模型模块
1. harness/__init__.py
空文件，用于将 harness 标记为 Python 包。
2. harness/models.py
包含所有数据结构定义：8 种错误类型枚举、6 个数据类，全部为无副作用的纯数据结构，支持模块间标准化通信。
python
运行
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Literal


class FailureType(Enum):
    """代码执行失败的分类枚举，共8种错误类型"""
    SYNTAX_ERROR = "SYNTAX_ERROR"
    NAME_ERROR = "NAME_ERROR"
    TYPE_ERROR = "TYPE_ERROR"
    IMPORT_ERROR = "IMPORT_ERROR"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    TIMEOUT = "TIMEOUT"
    ASSERTION_ERROR = "ASSERTION_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class Action:
    """Agent 执行动作的统一封装"""
    type: Literal["run_code", "write_file", "shell", "give_up"]
    payload: str


@dataclass
class RunResult:
    """代码执行器的运行结果输出"""
    stdout: str
    stderr: str
    exit_code: int
    elapsed: float
    timed_out: bool


@dataclass
class FailureInfo:
    """错误分类后的结构化信息，用于生成修复提示"""
    type: FailureType
    exception_class: str
    message: str
    line_no: int | None


@dataclass
class LoopResult:
    """Agent 主循环最终执行结果"""
    status: Literal["success", "failed", "stall", "hitl_pause", "give_up"]
    final_code: str | None
    rounds: int
    session_id: str


@dataclass
class RoundRecord:
    """单轮循环的记录，用于持久化到记忆模块"""
    round_no: int
    failure_type: str
    error_message: str
    action_taken: str
    guardrail_decision: str


@dataclass
class SessionSummary:
    """会话摘要，用于历史查询与上下文注入"""
    session_id: str
    created_at: str
    success: bool
    rounds: int
    failure_types: list[str]
3. tests/test_models.py
单元测试文件，覆盖核心字段校验、枚举完整性、可选字段等验证点。
python
运行
from harness.models import Action, RunResult, FailureInfo, FailureType, LoopResult, RoundRecord, SessionSummary


def test_action_fields():
    a = Action(type="run_code", payload="print(1)")
    assert a.type == "run_code"
    assert a.payload == "print(1)"


def test_run_result_fields():
    r = RunResult(stdout="hi", stderr="", exit_code=0, elapsed=0.1, timed_out=False)
    assert r.exit_code == 0
    assert not r.timed_out


def test_failure_type_enum():
    assert FailureType.SYNTAX_ERROR.value == "SYNTAX_ERROR"
    assert len(list(FailureType)) == 8


def test_loop_result_fields():
    lr = LoopResult(status="success", final_code="print(1)", rounds=2, session_id="abc")
    assert lr.status == "success"
    assert lr.rounds == 2


def test_failure_info_line_no_optional():
    fi = FailureInfo(type=FailureType.UNKNOWN, exception_class="", message="", line_no=None)
    assert fi.line_no is None
验证方式
在项目根目录执行测试命令：
bash
pytest tests/test_models.py -v
预期输出：5 个测试全部通过（5 passed）。
需要我继续实现 Task 2 的 LM 抽象层代码吗？