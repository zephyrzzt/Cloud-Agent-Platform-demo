# Cloud Agent Platform 完整架构与文件职责说明

# 一、项目定位

本项目是一个面向代码仓库和综合任务的云端 Agent 执行平台。

用户可以提交：

* GitHub 仓库地址；
* 分支、标签或 Commit；
* 自然语言任务；
* 模型供应商与模型名称；
* 仓库访问模式；
* Agent 运行时间、轮次、工具调用次数和 Token 预算；
* 可选的会话、回调和文件配置。

平台负责：

1. 创建任务和对话；
2. 持久化用户消息；
3. 调度任务；
4. 准备代码仓库和任务工作空间；
5. 创建安全隔离的执行沙箱；
6. 判断任务类型、复杂度和执行模式；
7. 选择单 Agent 或多 Agent 运行方式；
8. 调用 LLM；
9. 接收并执行工具调用；
10. 管理多智能体共享状态；
11. 检测测试、编译、运行等错误；
12. 管理 Agent 上下文与分层压缩；
13. 独立验证执行结果；
14. 保存报告、日志和任务产物；
15. 向前端可靠推送消息；
16. 向外部系统发送事件回调；
17. 删除沙箱并清理临时资源。

平台支持四类通用任务：

```text
编程任务 Coding
分析任务 Analysis
综合任务 Synthesis
报告任务 Report
```

复杂任务可以组合为：

```text
Mixed
```

例如：

> 分析指定代码仓库，定位认证模块问题，完成修复，运行测试并生成审查报告。

---

# 二、核心架构原则

## 1. 控制平面与执行平面分离

控制平面负责：

```text
任务
调度
模型
权限
状态
消息
文件
回调
```

执行平面负责：

```text
代码读取
代码搜索
代码修改
构建
测试
运行
```

执行平面位于 Docker、Kubernetes 或 Firecracker 沙箱中。

LLM、API 和任务调度器不能直接在宿主机执行用户代码。

---

## 2. LLM 只负责决策

LLM 可以决定：

* 查看哪些目录；
* 搜索哪些代码；
* 读取哪些文件；
* 是否修改文件；
* 是否运行测试；
* 是否需要其他 Agent；
* 是否进入下一阶段；
* 是否生成报告。

LLM 不能直接：

* 操作 Docker；
* 访问宿主机文件；
* 获取平台 API Key；
* 修改任务数据库；
* 操作 WebSocket；
* 直接调用远程系统；
* 自行绕过工具策略。

模型只能返回：

```text
文本结果
或
结构化 Tool Call
```

---

## 3. 工具调用必须经过统一管线

```text
ModelToolCall
→ ToolValidator
→ ToolPolicy
→ ExecutorRouter
→ ToolExecutor
→ Sandbox / MCP
→ ToolResult
→ 返回模型
```

其中：

```text
ToolValidator
负责参数是否合法

ToolPolicy
负责操作是否允许

ExecutorRouter
负责选择在哪里执行

ToolExecutor
负责真正执行
```

---

## 4. 多 Agent 共享状态，不共享完整上下文

Manager、Explorer、Developer、Reviewer 不互相传递全部聊天历史。

它们通过：

```text
Blackboard
```

共享结构化任务状态。

每个 Agent 维护独立：

```text
Context Lane
```

因此较小、短上下文模型也可以分别承担：

```text
研究
设计
开发
测试
审查
修复
```

---

## 5. 任务成功必须由 Verifier 判断

Agent 调用 `finish_task` 只表示：

> Agent 认为任务已经完成。

平台最终状态必须由独立 Verifier 确认。

---

## 6. 支撑能力与核心执行解耦

```text
Pending Messages
负责前端消息可靠投递

Event Callback
负责外部事件通知

File Storage
负责文件长期保存

MCP
负责扩展外部工具
```

关闭这些支撑模块后，核心 Agent 执行链路仍应能够运行。

---

# 三、系统总体架构

```text
Frontend / CLI / API
          ↓
Pending Messages
          ↓
Task Scheduler
          ↓
Task Worker
          ↓
Task Orchestrator
 ┌────────┼────────────────────────┐
 ↓        ↓                        ↓
Workspace Sandbox              Task Classifier
                                  ↓
                           Execution Router
                  ┌───────────────┼───────────────┐
                  ↓               ↓               ↓
              Single          Sequential         Sync
              Runner            Runner          Runner
                  │               │               │
                  └───────────────┴───────────────┘
                                  ↓
                              Agent Loop
                                  ↓
                           Model Provider
                                  ↓
                           Model Tool Call
                                  ↓
                           Tool Validator
                                  ↓
                             Tool Policy
                                  ↓
                           Executor Router
                         ┌────────┴────────┐
                         ↓                 ↓
                 Native Executor       MCP Executor
                         ↓                 ↓
                 Sandbox Service       MCP Manager

多 Agent 模式：
Manager
   ↓
Phase Router
   ↓
Delegation
   ↓
Explorer / Developer / Reviewer
   ↓
Blackboard + Failure Ledger
   ↓
Manager 再次决策

上下文：
Context Manager
├── Global Lane
├── Manager Lane
├── Explorer Lane
├── Developer Lane
└── Reviewer Lane

最终结果：
Verifier
   ↓
File Store
   ↓
Pending Messages + Event Callback
```

---

# 四、完整项目目录

```text
cloud-agent-platform/
├── app/
│   ├── main.py
│   │
│   ├── bootstrap/
│   │   ├── container.py
│   │   └── lifecycle.py
│   │
│   ├── api/
│   │   ├── task_api.py
│   │   ├── conversation_ws.py
│   │   ├── artifact_api.py
│   │   └── callback_api.py
│   │
│   ├── config/
│   │   └── settings.py
│   │
│   ├── domain/
│   │   ├── task.py
│   │   ├── repository.py
│   │   ├── conversation.py
│   │   └── event.py
│   │
│   ├── orchestration/
│   │   ├── models.py
│   │   ├── task_scheduler.py
│   │   ├── task_worker.py
│   │   ├── execution_lease.py
│   │   ├── task_orchestrator.py
│   │   ├── task_state_machine.py
│   │   ├── task_classifier.py
│   │   ├── execution_router.py
│   │   ├── phase_router.py
│   │   ├── execution_modes.py
│   │   ├── agent_loop.py
│   │   ├── retry_policy.py
│   │   ├── recovery_service.py
│   │   ├── errors.py
│   │   │
│   │   ├── runners/
│   │   │   ├── base.py
│   │   │   ├── single_agent.py
│   │   │   ├── sequential.py
│   │   │   └── sync_multi_agent.py
│   │   │
│   │   ├── multi_agent/
│   │   │   ├── models.py
│   │   │   ├── roles.py
│   │   │   ├── coordinator.py
│   │   │   ├── blackboard.py
│   │   │   ├── blackboard_store.py
│   │   │   ├── delegation.py
│   │   │   └── permissions.py
│   │   │
│   │   ├── failures/
│   │   │   ├── models.py
│   │   │   ├── detectors.py
│   │   │   ├── ledger.py
│   │   │   ├── fingerprint.py
│   │   │   └── circuit_breaker.py
│   │   │
│   │   └── reviewer_debug/
│   │       ├── models.py
│   │       ├── trigger.py
│   │       └── service.py
│   │
│   ├── context/
│   │   ├── models.py
│   │   ├── manager.py
│   │   ├── lane.py
│   │   ├── budget.py
│   │   ├── compaction_policy.py
│   │   ├── compactors.py
│   │   ├── file_buffer.py
│   │   ├── recall.py
│   │   └── errors.py
│   │
│   ├── pending_messages/
│   │   ├── models.py
│   │   ├── store.py
│   │   ├── service.py
│   │   ├── dispatcher.py
│   │   ├── replay_service.py
│   │   ├── retry_policy.py
│   │   ├── ordering.py
│   │   ├── connection_manager.py
│   │   ├── worker.py
│   │   └── errors.py
│   │
│   ├── event_callback/
│   │   ├── models.py
│   │   ├── config.py
│   │   ├── callback.py
│   │   ├── registry.py
│   │   ├── service.py
│   │   ├── dispatcher.py
│   │   ├── store.py
│   │   ├── signing.py
│   │   ├── retry_policy.py
│   │   ├── worker.py
│   │   ├── errors.py
│   │   └── providers/
│   │       ├── webhook.py
│   │       ├── in_process.py
│   │       └── message_queue.py
│   │
│   ├── file_storage/
│   │   ├── models.py
│   │   ├── config.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── factory.py
│   │   ├── path_policy.py
│   │   ├── errors.py
│   │   └── providers/
│   │       ├── local.py
│   │       ├── memory.py
│   │       ├── s3.py
│   │       ├── gcs.py
│   │       └── azure_blob.py
│   │
│   ├── workspace/
│   │   ├── workspace_manager.py
│   │   └── repository_preparer.py
│   │
│   ├── sandbox/
│   │   ├── models.py
│   │   ├── capabilities.py
│   │   ├── policy.py
│   │   ├── service.py
│   │   ├── healthcheck.py
│   │   ├── image_manager.py
│   │   ├── errors.py
│   │   └── providers/
│   │       ├── docker.py
│   │       ├── kubernetes.py
│   │       └── firecracker.py
│   │
│   ├── llm/
│   │   ├── models.py
│   │   ├── provider.py
│   │   ├── config.py
│   │   ├── capabilities.py
│   │   ├── model_catalog.py
│   │   ├── registry.py
│   │   ├── router.py
│   │   ├── retry_policy.py
│   │   ├── usage_tracker.py
│   │   ├── errors.py
│   │   ├── adapters/
│   │   │   ├── message_adapter.py
│   │   │   └── tool_schema_adapter.py
│   │   └── providers/
│   │       ├── openai.py
│   │       ├── anthropic.py
│   │       ├── google.py
│   │       ├── openai_compatible.py
│   │       └── mock.py
│   │
│   ├── tools/
│   │   ├── models.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── validator.py
│   │   ├── policy.py
│   │   ├── native/
│   │   │   ├── file_tools.py
│   │   │   ├── search_tools.py
│   │   │   ├── command_tools.py
│   │   │   └── artifact_tools.py
│   │   └── executors/
│   │       ├── base.py
│   │       ├── router.py
│   │       ├── native_executor.py
│   │       └── mcp_executor.py
│   │
│   ├── integrations/
│   │   └── mcp/
│   │       ├── models.py
│   │       ├── config.py
│   │       ├── client.py
│   │       ├── manager.py
│   │       ├── tool_adapter.py
│   │       ├── auth.py
│   │       └── errors.py
│   │
│   ├── verification/
│   │   ├── models.py
│   │   ├── verifier.py
│   │   └── todo_report_verifier.py
│   │
│   ├── observability/
│   │   ├── logging.py
│   │   ├── metrics.py
│   │   ├── tracing.py
│   │   └── audit.py
│   │
│   └── storage/
│       ├── task_store.py
│       ├── conversation_store.py
│       └── event_store.py
│
├── sandbox/
│   └── Dockerfile
│
├── docs/
│   ├── architecture.md
│   ├── execution-flow.md
│   ├── orchestration-design.md
│   ├── multi-agent-design.md
│   ├── blackboard-design.md
│   ├── context-design.md
│   ├── failure-ledger-design.md
│   ├── sandbox-design.md
│   ├── llm-tool-design.md
│   ├── messaging-design.md
│   ├── callback-design.md
│   ├── file-storage-design.md
│   └── security-design.md
│
├── tests/
│   ├── orchestration/
│   ├── context/
│   ├── sandbox/
│   ├── llm/
│   ├── tools/
│   ├── integration/
│   └── end_to_end/
│
├── demo.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# 五、入口与依赖装配

## 1. `app/main.py`

### 作用

应用程序入口。

主要负责：

* 创建 FastAPI 或 CLI 应用；
* 调用依赖容器；
* 注册 API 路由；
* 注册系统启动和关闭事件；
* 启动应用。

### 不应该负责

* 创建每个具体 Provider；
* 直接调用模型；
* 执行任务；
* 直接操作 Docker；
* 编写业务逻辑。

---

## 2. `app/bootstrap/container.py`

### 作用

系统的 Composition Root，即依赖装配中心。

负责创建：

```text
Settings
TaskStore
ConversationStore
EventStore
PendingMessageStore
CallbackStore
FileStore
SandboxService
ModelProvider Registry
Tool Registry
Executor Router
Agent Runners
Task Scheduler
Task Worker
Task Orchestrator
Verifier
```

所有依赖在这里统一连接。

这样业务模块不会在内部随意：

```python
OpenAIProvider()
DockerSandboxService()
LocalFileStore()
```

---

## 3. `app/bootstrap/lifecycle.py`

### 作用

管理系统生命周期。

启动时：

* 启动 TaskWorker；
* 启动 PendingMessageWorker；
* 启动 EventCallbackWorker；
* 建立 MCP 连接；
* 执行遗留任务恢复；
* 检查文件目录；
* 检查沙箱运行环境。

关闭时：

* 停止领取新任务；
* 等待正在处理的任务；
* 关闭 Worker；
* 关闭 HTTP 客户端；
* 关闭 MCP 会话；
* 释放数据库连接。

---

# 六、API 层

## 1. `api/task_api.py`

### 作用

提供任务相关 HTTP API。

建议接口：

```text
POST   /tasks
GET    /tasks/{task_id}
GET    /tasks/{task_id}/events
GET    /tasks/{task_id}/result
DELETE /tasks/{task_id}
```

负责：

* 校验用户请求；
* 创建 Task；
* 将任务放入 Scheduler；
* 查询任务状态；
* 取消任务；
* 返回任务结果。

不直接调用 Agent。

---

## 2. `api/conversation_ws.py`

### 作用

处理前端 WebSocket 对话连接。

负责：

* 建立连接；
* 用户身份和会话权限验证；
* 接收用户消息；
* 创建入站 PendingMessage；
* 接收 ACK；
* 前端重连后补发消息；
* 连接断开时注销 Session。

不能直接调用 AgentLoop。

---

## 3. `api/artifact_api.py`

### 作用

提供任务产物和附件的上传、查询与下载。

建议接口：

```text
GET  /tasks/{task_id}/artifacts
GET  /files/{file_id}
POST /conversations/{conversation_id}/attachments
```

通过 FileStore 操作文件，不直接读取任意本地路径。

---

## 4. `api/callback_api.py`

### 作用

管理外部事件订阅。

负责：

* 创建 Webhook；
* 查看订阅；
* 修改订阅；
* 禁用订阅；
* 查看投递记录；
* 手动重试失败投递。

需要严格防止 SSRF 和无权限创建内网回调。

---

# 七、系统配置

## `config/settings.py`

### 作用

统一读取和校验环境配置。

包括：

```text
数据库地址
Workspace根目录
沙箱镜像
沙箱资源限制
任务并发数
Agent轮次限制
模型配置
API Key
文件存储配置
消息重试配置
回调配置
MCP配置
日志级别
```

所有密钥只存在可信控制平面。

---

# 八、领域模型层

## 1. `domain/task.py`

### 作用

定义任务领域对象。

建议包含：

```text
Task
TaskRequest
TaskStatus
TaskLimits
TaskResult
TaskPriority
ExecutionMode
```

### TaskStatus

```text
CREATED
QUEUED
SCHEDULED
PREPARING
SANDBOX_STARTING
RUNNING
WAITING_INPUT
VERIFYING
SUCCEEDED
FAILED
TIMEOUT
CANCELLED
```

---

## 2. `domain/repository.py`

### 作用

描述代码仓库来源。

建议包含：

```text
RepositorySource
RepositoryProvider
RepositoryAccessMode
PreparedWorkspace
```

RepositoryAccessMode：

```text
READ_ONLY
READ_WRITE_COPY
```

`READ_WRITE_COPY` 表示只允许修改任务副本。

---

## 3. `domain/conversation.py`

### 作用

定义对话及其消费位置。

建议包含：

```text
Conversation
ConversationStatus
ConversationOffset
ConversationParticipant
```

ConversationOffset 保存：

```text
next_inbound_sequence
next_outbound_sequence
last_processed_inbound_sequence
last_acked_outbound_sequence
```

---

## 4. `domain/event.py`

### 作用

定义不可变业务事件。

建议事件：

```text
TASK_CREATED
TASK_QUEUED
TASK_STARTED
WORKSPACE_PREPARED
SANDBOX_READY
MODEL_REQUESTED
MODEL_RESPONDED
TOOL_STARTED
TOOL_COMPLETED
FAILURE_DETECTED
BLACKBOARD_UPDATED
PHASE_CHANGED
ARTIFACT_CREATED
TASK_COMPLETED
TASK_FAILED
```

Event 用于：

* 审计；
* 调试；
* 前端推送；
* 外部回调；
* 任务恢复。

---

# 九、Agent 编排与调度

## 1. `orchestration/models.py`

### 作用

定义编排层内部模型。

建议包含：

```text
TaskExecutionContext
TaskProfile
AgentRunState
AgentAction
AgentObservation
AgentRunResult
StopReason
RetryDecision
```

### StopReason

```text
COMPLETED
MAX_TURNS
TIMEOUT
TOKEN_BUDGET_EXCEEDED
TOOL_FAILURE_LIMIT
REPEATED_ACTION
CANCELLED
WAITING_USER_INPUT
MODEL_ERROR
SANDBOX_ERROR
```

---

## 2. `task_scheduler.py`

### 作用

处理平台级任务调度。

负责：

* 按顺序领取任务；
* 控制最大并发数；
* 检查用户配额；
* 检查沙箱容量；
* 检查任务优先级；
* 避免已取消任务进入执行；
* 为 Worker 分配任务。

第一版可采用：

```text
FIFO + 最大并发数
```

---

## 3. `task_worker.py`

### 作用

后台任务执行 Worker。

流程：

```text
领取任务
→ 获取 Execution Lease
→ 调用 TaskOrchestrator
→ 保存执行结果
→ 释放 Lease
```

Worker 不处理 Agent 内部阶段。

---

## 4. `execution_lease.py`

### 作用

防止同一个任务被多个 Worker 同时执行。

字段：

```text
task_id
worker_id
lease_token
acquired_at
expires_at
heartbeat_at
```

Worker 定期续约。

租约过期后，任务才允许重新领取。

---

## 5. `task_orchestrator.py`

### 作用

管理单个任务完整生命周期。

主要流程：

```text
准备Workspace
→ 拉取仓库
→ 创建Sandbox
→ 等待READY
→ 分类任务
→ 选择Runner
→ 执行Agent
→ 验证结果
→ 保存产物
→ 清理Sandbox
```

必须在 `finally` 中清理资源。

不负责具体 LLM Tool Loop。

---

## 6. `task_state_machine.py`

### 作用

统一管理任务状态转换。

合法示例：

```text
CREATED → QUEUED
QUEUED → SCHEDULED
SCHEDULED → PREPARING
PREPARING → SANDBOX_STARTING
SANDBOX_STARTING → RUNNING
RUNNING → VERIFYING
VERIFYING → SUCCEEDED
```

阻止非法转换。

---

## 7. `task_classifier.py`

### 作用

分析任务性质。

输出 TaskProfile：

```text
task_kind
complexity
risk
required_phases
required_tools
required_capabilities
recommended_mode
```

任务种类：

```text
CODING
ANALYSIS
SYNTHESIS
REPORT
MIXED
```

第一版建议使用规则分类，复杂情况再调用 LLM 辅助分类。

---

## 8. `execution_modes.py`

### 作用

定义执行模式：

```text
SINGLE
SEQUENTIAL
SYNC
```

SINGLE：一个 Agent。

SEQUENTIAL：多个角色顺序执行。

SYNC：Manager 根据状态动态委派。

---

## 9. `execution_router.py`

### 作用

根据 TaskProfile 选择执行 Runner。

示例规则：

```text
简单搜索或报告
→ SingleAgentRunner

需要研究、实现、审查
→ SequentialRunner

复杂长线任务
→ SyncMultiAgentRunner
```

---

## 10. `phase_router.py`

### 作用

根据任务当前阶段选择 Agent。

阶段：

```text
RESEARCH
DESIGN
IMPLEMENT
TEST
REVIEW
DEPLOY
COMPLETED
```

默认路由：

```text
RESEARCH  → Explorer
DESIGN    → Manager
IMPLEMENT → Developer
TEST      → Reviewer
REVIEW    → Reviewer
DEPLOY    → Developer
```

允许阶段回退。

---

## 11. `agent_loop.py`

### 作用

实现最小 Agent 循环。

```text
LLM
→ tool_use
→ tool_result
→ LLM
→ loop
```

负责：

* 调用 ModelProvider；
* 解析 Tool Call；
* 调用工具管线；
* 将 ToolResult 写回 Context；
* 统计轮次、时间与 Token；
* 判断停止条件；
* 返回 AgentRunResult。

它不负责：

* 任务调度；
* 沙箱创建；
* 多 Agent 协调；
* 文件长期保存。

---

## 12. `retry_policy.py`

### 作用

统一任务级和阶段级重试决策。

区分：

```text
可重试错误
不可重试错误
需要切换Agent的错误
需要回退阶段的错误
需要用户输入的错误
```

---

## 13. `recovery_service.py`

### 作用

恢复异常中断任务。

检查：

* RUNNING 任务 Lease 是否过期；
* 沙箱是否仍存在；
* Blackboard 是否有快照；
* 最近 Agent 阶段；
* 最近 Event；
* 是否能继续执行。

第一版至少处理：

```text
僵尸RUNNING任务
遗留Docker容器
过期Execution Lease
```

---

## 14. `orchestration/errors.py`

定义：

```text
OrchestrationError
InvalidTaskTransitionError
TaskLeaseError
TaskRoutingError
AgentLoopError
TaskRecoveryError
ExecutionBudgetExceededError
```

---

# 十、Runner 模块

## 1. `runners/base.py`

定义统一 Runner 接口：

```text
run(execution_context) → AgentRunResult
```

---

## 2. `runners/single_agent.py`

### 作用

执行简单单 Agent 任务。

特点：

* 使用 Global Context Lane；
* 不需要角色协作；
* 不需要复杂 Blackboard；
* 直接复用 AgentLoop。

适合 TODO 扫描、分析和简单报告。

---

## 3. `runners/sequential.py`

### 作用

按固定角色顺序执行。

典型流程：

```text
Explorer
→ Developer
→ Reviewer
```

每个角色完成后写入 Blackboard，下一角色读取结构化结果。

---

## 4. `runners/sync_multi_agent.py`

### 作用

实现 Manager 主导的动态协作。

流程：

```text
Manager读取Blackboard
→ 判断当前阶段
→ 创建Delegation
→ 目标Agent执行
→ 更新Blackboard
→ Manager再次判断
```

支持阶段回退和反复修复。

---

# 十一、多 Agent 模块

## 1. `multi_agent/models.py`

定义：

```text
AgentRole
AgentRoleConfig
AgentIdentity
DelegationRequest
DelegationResult
BlackboardPatch
AgentPermissionSet
```

---

## 2. `roles.py`

### 作用

定义四个角色的职责、提示词和默认权限。

Manager：

* 路由；
* 阶段管理；
* 预算分配；
* 完成判断。

Explorer：

* 仓库探索；
* 搜索；
* 依赖分析；
* 证据收集。

Developer：

* 修改代码；
* 实现功能；
* 构建和测试。

Reviewer：

* 测试；
* 审查；
* 错误判断；
* 通过或阻塞。

---

## 3. `coordinator.py`

### 作用

协调多 Agent 执行。

负责：

* 调用 Manager；
* 创建委派；
* 选择目标角色；
* 调用目标角色 AgentLoop；
* 应用 BlackboardPatch；
* 更新任务阶段；
* 调用 Circuit Breaker。

---

## 4. `blackboard.py`

### 作用

定义单任务共享状态。

建议字段：

```text
original_goal
task_kind
execution_mode
current_phase
current_step
plan
research_notes
design_decisions
code_artifacts
touched_files
execution_evidence
review_feedback
failure_summary
todos
budget
approval_state
version
```

Blackboard 是当前状态，不是完整事件历史。

---

## 5. `blackboard_store.py`

### 作用

持久化 Blackboard。

负责：

* 创建初始状态；
* 保存快照；
* 按版本更新；
* 乐观锁；
* 防止并发覆盖；
* 查询最新版本；
* 恢复任务状态。

---

## 6. `delegation.py`

### 作用

创建结构化 Agent 委派。

DelegationRequest 包含：

```text
目标Agent
当前阶段
具体目标
允许工具
Token预算
最大轮次
所需证据
完成标准
```

避免 Manager 只发送模糊自然语言。

---

## 7. `permissions.py`

### 作用

定义各角色默认工具权限。

例如：

```text
Explorer
    只读

Developer
    读写任务副本、测试、构建

Reviewer
    默认只读和测试

Manager
    不直接写代码
```

Reviewer Debug Mode 的临时权限也通过此处检查。

---

# 十二、Failure Ledger

## 1. `failures/models.py`

定义六类错误：

```text
TEST
LINT
COMPILATION
BUILD
DEPLOY
RUNTIME
```

FailureRecord 字段：

```text
failure_id
category
phase
source_tool
command
exit_code
message
fingerprint
evidence_refs
affected_files
owner
status
attempt_count
first_seen_at
last_seen_at
resolved_at
```

状态：

```text
OPEN
DIAGNOSING
FIXING
RESOLVED
REGRESSED
IGNORED
```

---

## 2. `failures/detectors.py`

### 作用

从确定性执行结果中检测错误。

检测来源：

* 退出码；
* 测试结果；
* Lint 输出；
* 编译器输出；
* 构建日志；
* Traceback；
* 部署响应。

可以实现 Detector Chain。

---

## 3. `failures/ledger.py`

### 作用

管理统一错误账本。

负责：

* 新增错误；
* 合并重复错误；
* 指定 Owner；
* 更新修复状态；
* 标记已解决；
* 检测回归；
* 提供未解决错误列表。

---

## 4. `failures/fingerprint.py`

### 作用

将错误归一化后生成指纹。

防止相同错误被重复记录。

指纹可根据：

```text
错误类别
规范化错误信息
文件
行号
命令
```

生成。

---

## 5. `failures/circuit_breaker.py`

### 作用

防止 Agent 无效死循环。

检测：

* 相同错误重复出现；
* 同一工具参数反复执行；
* 多轮无新证据；
* 多轮无新文件修改；
* Developer 与 Reviewer 反复往返；
* Blackboard 无实质变化。

决策：

```text
CONTINUE
SWITCH_AGENT
RETURN_TO_RESEARCH
REQUEST_USER_INPUT
STOP_TASK
```

---

# 十三、Reviewer Debug Mode

## 1. `reviewer_debug/models.py`

定义：

```text
DebugModeStatus
DebugPermissionGrant
DebugSession
DebugResult
```

DebugPermissionGrant 包含：

```text
allowed_tools
allowed_paths
max_rounds
expires_at
reason
```

---

## 2. `reviewer_debug/trigger.py`

### 作用

判断是否应进入 Debug Mode。

条件：

* Failure Ledger 有未解决错误；
* 错误证据明确；
* Reviewer 可独立修复；
* 仍有预算；
* 任务未取消。

---

## 3. `reviewer_debug/service.py`

### 作用

管理 Debug Mode 生命周期。

负责：

* 发放临时写权限；
* 限制写入路径；
* 记录调试轮数；
* 调用 Reviewer AgentLoop；
* 错误解决后撤销权限；
* 达到阈值后退回 Developer；
* 记录审计事件。

Reviewer 仍必须通过 ToolPolicy 和 SandboxService。

---

# 十四、上下文管理

## 1. `context/models.py`

定义：

```text
ContextLane
ContextItem
ContextObjectRef
ContextSnapshot
CompactionLevel
ContextBudget
```

CompactionLevel：

```text
NORMAL
LIGHT
MEDIUM
HEAVY
```

---

## 2. `context/manager.py`

### 作用

统一管理 Agent 上下文。

负责：

* 创建 Context Lane；
* 追加消息；
* 追加 ToolResult；
* 生成模型输入；
* 触发压缩；
* 获取 Blackboard 视图；
* 获取 Failure 视图；
* 生成 Checkpoint。

---

## 3. `context/lane.py`

### 作用

实现分 Agent 独立上下文。

支持：

```text
global
manager
explorer
developer
reviewer
```

Single 模式只使用 global。

每个 Lane 单独压缩，不影响其他角色。

---

## 4. `context/budget.py`

### 作用

计算上下文预算。

考虑：

* 模型最大 Context Window；
* System Prompt；
* Tool Schema；
* 预留输出 Token；
* Blackboard；
* Failure Ledger；
* 对话历史。

决定何时触发 Light、Medium 或 Heavy。

---

## 5. `context/compaction_policy.py`

### 作用

根据上下文压力选择压缩等级。

示例：

```text
低于60%
→ NORMAL

60%—75%
→ LIGHT

75%—90%
→ MEDIUM

超过90%
→ HEAVY
```

阈值应可配置。

---

## 6. `context/compactors.py`

### 作用

实现具体压缩策略。

Normal：

* 保留完整近期内容。

Light：

* 截断 stdout；
* 合并重复结果；
* 删除无意义内容。

Medium：

* 将旧历史总结为结构化摘要。

Heavy：

* 原始内容卸载；
* 只保留状态快照、关键证据和引用。

---

## 7. `context/file_buffer.py`

### 作用

将大型上下文内容卸载到 FileStore。

适合：

* 构建日志；
* 大型搜索结果；
* 完整 Diff；
* 长代码文件；
* 测试日志。

上下文只保存：

```text
摘要
FileRef
来源ToolCall
Token估算
召回提示
```

---

## 8. `context/recall.py`

### 作用

按需召回已卸载内容。

Agent 需要时：

```text
ContextObjectRef
→ FileStore
→ 按范围读取
→ 注入当前Lane
```

---

## 9. `context/errors.py`

定义：

```text
ContextError
ContextBudgetExceededError
CompactionError
ContextRecallError
ContextLaneNotFoundError
```

---

# 十五、Pending Messages

## 1. `pending_messages/models.py`

定义：

```text
PendingMessage
MessageDirection
MessageStatus
MessageType
MessageDependency
AckRequest
ReplayRequest
```

状态：

```text
PENDING
WAITING_DEPENDENCY
READY
IN_FLIGHT
ACKED
RETRY_WAIT
DEAD_LETTER
CANCELLED
EXPIRED
```

---

## 2. `pending_messages/store.py`

### 作用

保存消息投递状态。

接口：

```text
enqueue
claim_next
mark_in_flight
mark_acked
mark_retry
list_after_sequence
release_expired_leases
```

---

## 3. `pending_messages/service.py`

### 作用

可靠消息业务入口。

负责：

* 创建入站消息；
* 创建出站消息；
* 幂等去重；
* 分配序列号；
* 处理 ACK；
* 释放等待消息；
* 取消消息。

---

## 4. `pending_messages/dispatcher.py`

### 作用

分发一次消息。

入站消息：

```text
检查顺序
→ 检查任务和沙箱
→ 交给任务系统
```

出站消息：

```text
检查WebSocket
→ 在线发送
→ 离线等待补发
```

---

## 5. `pending_messages/replay_service.py`

### 作用

前端重连后按序补发消息。

查询：

```text
sequence > last_acked_sequence
```

---

## 6. `pending_messages/retry_policy.py`

负责：

* 指数退避；
* 随机抖动；
* 最大尝试次数；
* 区分可重试和不可重试错误。

---

## 7. `pending_messages/ordering.py`

保证：

* 同一会话入站消息按序执行；
* 出站消息按序发送；
* 不同会话允许并发。

---

## 8. `pending_messages/connection_manager.py`

管理当前 WebSocket 连接。

不保存可靠消息，只管理在线连接。

---

## 9. `pending_messages/worker.py`

后台领取和发送消息。

处理 ACK 超时、租约恢复和死信。

---

## 10. `pending_messages/errors.py`

定义：

```text
MessageNotFoundError
DuplicateMessageError
InvalidAckError
OrderingViolationError
MessageLeaseError
RetryExhaustedError
```

---

# 十六、Event Callback

## 1. `event_callback/models.py`

定义：

```text
CallbackSubscription
CallbackDelivery
CallbackAttempt
CallbackPayload
CallbackResult
CallbackKind
CallbackStatus
```

---

## 2. `event_callback/config.py`

配置：

* 超时；
* 重试次数；
* HTTPS 要求；
* 域名白名单；
* SSRF 限制；
* Worker 间隔；
* 签名算法。

---

## 3. `event_callback/callback.py`

定义统一 Callback 接口：

```text
send(delivery, event)
validate()
kind
```

---

## 4. `event_callback/registry.py`

注册：

```text
webhook
in_process
message_queue
```

---

## 5. `event_callback/service.py`

负责：

* 创建订阅；
* 匹配事件；
* 创建 Delivery；
* 禁用订阅；
* 手动重试；
* 防止重复投递。

---

## 6. `event_callback/dispatcher.py`

执行单次事件通知。

---

## 7. `event_callback/store.py`

保存：

* 订阅；
* 投递任务；
* 尝试记录；
* 重试状态；
* 死信状态。

---

## 8. `event_callback/signing.py`

为 Webhook 生成 HMAC-SHA256 签名。

---

## 9. `event_callback/retry_policy.py`

区分：

```text
HTTP 408、429、5xx
→ 通常重试

HTTP 400、401、403
→ 通常不重试
```

---

## 10. `event_callback/worker.py`

后台异步投递 Webhook。

---

## 11. `event_callback/errors.py`

统一 Callback 异常。

---

## 12. `providers/webhook.py`

通过 HTTP 发送签名 Webhook。

需要防止 SSRF 和危险重定向。

---

## 13. `providers/in_process.py`

执行平台内部函数回调，适合测试和内部扩展。

---

## 14. `providers/message_queue.py`

预留 Kafka、RabbitMQ、SNS、Pub/Sub 等实现。

---

# 十七、File Storage

## 1. `file_storage/models.py`

定义：

```text
FileRef
FileMetadata
FileObject
FileListPage
FileStoreKind
```

---

## 2. `file_storage/config.py`

定义带 `kind` 判别字段的配置：

```text
local
memory
s3
gcs
azure_blob
```

---

## 3. `file_storage/base.py`

定义 FileStore 统一接口：

```text
put_bytes
put_stream
get_bytes
open_reader
exists
stat
delete
list
copy
move
generate_download_url
```

---

## 4. `file_storage/registry.py`

注册不同存储实现。

---

## 5. `file_storage/factory.py`

根据配置的 `kind` 创建具体 FileStore。

---

## 6. `file_storage/path_policy.py`

检查文件 Key：

* 禁止绝对路径；
* 禁止 `../`；
* 禁止跨任务访问；
* 禁止控制字符；
* 限制文件大小。

---

## 7. `file_storage/errors.py`

定义统一文件存储异常。

---

## 8. `providers/local.py`

将文件保存到本地文件系统。

适合开发和单机部署。

---

## 9. `providers/memory.py`

内存存储，适合测试。

---

## 10. `providers/s3.py`

支持 AWS S3、MinIO、R2 等兼容存储。

---

## 11. `providers/gcs.py`

支持 Google Cloud Storage。

---

## 12. `providers/azure_blob.py`

支持 Azure Blob Storage。

---

# 十八、Workspace

## 1. `workspace/workspace_manager.py`

### 作用

管理任务执行时的本地临时目录。

```text
task-root/
├── repository/
├── artifacts/
├── logs/
└── metadata/
```

负责创建、权限控制、路径检查和清理。

---

## 2. `workspace/repository_preparer.py`

### 作用

在可信控制平面获取代码仓库。

负责：

* 校验仓库地址；
* 校验 Ref；
* 浅克隆；
* Git 超时；
* 私有仓库临时 Token；
* 克隆失败清理；
* 禁止交互式认证。

Git Token 不进入 LLM 和沙箱。

---

# 十九、Sandbox

## 1. `sandbox/models.py`

定义：

```text
SandboxStatus
SandboxSpec
SandboxInfo
CommandSpec
CommandResult
NetworkPolicy
MountSpec
ResourceLimits
```

CommandSpec 使用结构化命令：

```text
argv
working_directory
environment
stdin
timeout_seconds
max_output_bytes
```

避免默认执行任意 Shell 字符串。

---

## 2. `sandbox/capabilities.py`

定义运行时能力：

```text
EXEC
PAUSE_RESUME
NETWORK_CONTROL
READ_ONLY_ROOT
RESOURCE_LIMITS
SNAPSHOT
EXPOSE_PORT
FILE_TRANSFER
```

---

## 3. `sandbox/policy.py`

统一管理：

* 镜像白名单；
* 挂载路径；
* 网络规则；
* 环境变量白名单；
* CPU、内存、PID 上限；
* 命令时长；
* 输出长度；
* 可写路径。

---

## 4. `sandbox/service.py`

定义统一沙箱接口：

```text
start_sandbox
get_sandbox
wait_until_ready
execute
pause
resume
delete
```

---

## 5. `sandbox/healthcheck.py`

检查：

* 容器进程；
* 工作目录；
* 仓库挂载；
* 产物目录；
* 必要工具；
* 非 root 用户。

只有通过后才进入 READY。

---

## 6. `sandbox/image_manager.py`

选择和校验沙箱镜像。

根据：

* 编程语言；
* 所需工具；
* 镜像版本；
* 安全策略；

选择镜像。

---

## 7. `sandbox/errors.py`

统一沙箱异常：

```text
SandboxNotFoundError
SandboxNotReadyError
SandboxStartError
SandboxExecutionError
SandboxTimeoutError
SandboxPolicyViolationError
SandboxResourceLimitError
```

---

## 8. `providers/docker.py`

实现 Docker 沙箱：

* 容器创建；
* 目录挂载；
* 非 root；
* 只读根文件系统；
* Capability Drop；
* no-new-privileges；
* CPU、内存、PID 限制；
* 网络控制；
* Exec；
* 输出截断；
* 容器清理。

---

## 9. `providers/kubernetes.py`

预留 Kubernetes Pod 沙箱实现。

---

## 10. `providers/firecracker.py`

预留 Firecracker microVM 强隔离实现。

---

# 二十、LLM 集成

## 1. `llm/models.py`

定义统一模型对象：

```text
ChatMessage
ModelRequest
ModelResponse
ModelToolCall
TokenUsage
FinishReason
ModelMetadata
```

---

## 2. `llm/provider.py`

定义统一 Provider 接口：

```text
generate
stream
supports
validate_config
```

---

## 3. `llm/config.py`

定义：

```text
ProviderConfig
ModelConfig
ModelSelection
FallbackConfig
```

Provider 与具体 Model 分离。

---

## 4. `llm/capabilities.py`

定义：

```text
TOOL_CALLING
STRUCTURED_OUTPUT
STREAMING
VISION
REASONING
LONG_CONTEXT
PARALLEL_TOOL_CALLS
PROMPT_CACHING
```

---

## 5. `llm/model_catalog.py`

保存模型元数据：

```text
provider
model_name
context_window
max_output_tokens
capabilities
cost_profile
```

---

## 6. `llm/registry.py`

管理 Provider 实例。

新增模型厂商时只需注册新的 Provider。

---

## 7. `llm/router.py`

根据：

* Agent 角色；
* 任务复杂度；
* 所需能力；
* 上下文长度；
* 成本；
* 服务可用性；

选择 Provider 和模型。

---

## 8. `llm/retry_policy.py`

区分可重试和不可重试模型错误。

---

## 9. `llm/usage_tracker.py`

统计：

* 输入 Token；
* 输出 Token；
* 缓存 Token；
* 模型调用次数；
* Agent 角色用量；
* 重试次数；
* 调用耗时。

---

## 10. `llm/errors.py`

统一厂商异常。

---

## 11. `adapters/message_adapter.py`

将平台 ChatMessage 转换为厂商消息格式。

---

## 12. `adapters/tool_schema_adapter.py`

将平台 ToolDefinition 转换为厂商 Tool Schema。

---

## 13. `providers/openai.py`

适配 OpenAI 模型接口。

---

## 14. `providers/anthropic.py`

适配 Anthropic 模型接口。

---

## 15. `providers/google.py`

适配 Google 模型接口。

---

## 16. `providers/openai_compatible.py`

适配本地模型、vLLM 和兼容接口。

---

## 17. `providers/mock.py`

返回预设响应，用于测试 AgentLoop。

---

# 二十一、工具系统

## 1. `tools/models.py`

定义：

```text
ToolDefinition
ToolRequest
ToolResult
ToolContext
ToolRiskLevel
ToolExecutionTarget
PolicyDecision
```

---

## 2. `tools/base.py`

定义原生工具接口：

```text
definition
validate
execute
```

---

## 3. `tools/registry.py`

注册原生工具和 MCP 工具。

---

## 4. `tools/validator.py`

检查工具参数 Schema 和类型。

---

## 5. `tools/policy.py`

检查：

* 角色权限；
* 路径边界；
* 网络权限；
* 敏感文件；
* 远程写入；
* Reviewer Debug Grant；
* 工具风险等级。

---

## 6. `native/file_tools.py`

提供：

```text
list_files
read_file
write_file
edit_file
```

写工具只在任务允许时注册。

---

## 7. `native/search_tools.py`

提供：

```text
search_code
find_symbol
```

底层可调用 ripgrep。

---

## 8. `native/command_tools.py`

提供受控命令：

```text
run_test
run_lint
run_build
run_compile
run_program
```

不提供完全自由的 Shell。

---

## 9. `native/artifact_tools.py`

提供：

```text
write_artifact
list_artifacts
finish_task
```

---

## 10. `executors/base.py`

定义 ToolExecutor 接口：

```text
execute(tool_request, context)
```

---

## 11. `executors/router.py`

根据执行目标选择 Executor。

---

## 12. `executors/native_executor.py`

通过 SandboxService 执行原生工具。

---

## 13. `executors/mcp_executor.py`

通过 MCPManager 执行远程 MCP 工具。

---

# 二十二、MCP 集成

## 1. `integrations/mcp/models.py`

定义 MCP Server、Tool 和 Result 的内部模型。

---

## 2. `integrations/mcp/config.py`

定义 stdio、HTTP 等 MCP Server 配置。

---

## 3. `integrations/mcp/client.py`

管理单个 MCP Server 连接。

---

## 4. `integrations/mcp/manager.py`

管理多个 MCP Server。

---

## 5. `integrations/mcp/tool_adapter.py`

将 MCP Tool 转换为平台 ToolDefinition。

---

## 6. `integrations/mcp/auth.py`

管理 Token、API Key 和 OAuth。

认证信息不进入模型上下文。

---

## 7. `integrations/mcp/errors.py`

统一 MCP 异常。

---

# 二十三、验证模块

## 1. `verification/models.py`

定义：

```text
VerificationResult
VerificationCheck
VerificationStatus
```

---

## 2. `verification/verifier.py`

定义统一验证接口。

---

## 3. `verification/todo_report_verifier.py`

检查：

* 报告存在；
* 报告非空；
* TODO、FIXME、HACK 数量；
* 文件路径；
* 行号；
* 源码是否被修改；
* 报告格式。

---

# 二十四、可观测性

## 1. `observability/logging.py`

输出结构化日志：

```text
task_id
conversation_id
agent_role
agent_turn
sandbox_id
tool_call_id
event_id
```

---

## 2. `observability/metrics.py`

统计：

* 成功率；
* 沙箱启动时间；
* 模型耗时；
* 工具耗时；
* Token 用量；
* Agent 轮次；
* 重试次数；
* Failure 数量。

---

## 3. `observability/tracing.py`

建立完整调用链：

```text
Task
├── Repository
├── Sandbox
├── Agent Turn
│   ├── Model
│   └── Tool
└── Verification
```

---

## 4. `observability/audit.py`

记录：

* 高风险工具调用；
* 权限拒绝；
* Reviewer Debug 授权；
* 外部写入；
* 文件修改；
* MCP 写操作。

---

# 二十五、元数据存储

## 1. `storage/task_store.py`

保存 Task 和状态。

---

## 2. `storage/conversation_store.py`

保存 Conversation 和消息消费位置。

---

## 3. `storage/event_store.py`

保存不可变 Event。

第一版可以使用 SQLite，后续替换 PostgreSQL。

---

# 二十六、沙箱镜像

## `sandbox/Dockerfile`

定义基础沙箱环境。

第一版安装：

```text
Shell
Git
ripgrep
coreutils
Python
```

还需要：

* 创建普通用户；
* 设置固定 UID；
* 设置工作目录；
* 不使用 root；
* 保持容器长期运行；
* 不写入密钥。

---

# 二十七、文档目录

## `docs/architecture.md`

总体分层、模块依赖和核心边界。

## `docs/execution-flow.md`

完整任务执行时序。

## `docs/orchestration-design.md`

Scheduler、Worker、Orchestrator、Runner 和 AgentLoop。

## `docs/multi-agent-design.md`

四角色职责、委派和执行模式。

## `docs/blackboard-design.md`

Blackboard 数据模型、版本控制和写入边界。

## `docs/context-design.md`

Context Lane、四级压缩和 File Buffer。

## `docs/failure-ledger-design.md`

六类错误、Fingerprint 和 Circuit Breaker。

## `docs/sandbox-design.md`

沙箱安全策略和运行时抽象。

## `docs/llm-tool-design.md`

Provider、Tool Call、Validator、Policy 和 Executor。

## `docs/messaging-design.md`

Pending Messages、ACK 和断线补发。

## `docs/callback-design.md`

Webhook、签名、重试和死信。

## `docs/file-storage-design.md`

FileStore 接口及多后端。

## `docs/security-design.md`

凭证边界、Prompt Injection、沙箱、路径、网络和权限。

---

# 二十八、测试目录

## `tests/orchestration/`

测试：

* AgentLoop；
* Scheduler；
* Execution Lease；
* 状态机；
* Single Runner；
* Sequential Runner；
* 多 Agent 路由；
* Recovery。

## `tests/context/`

测试：

* Context Lane；
* Token Budget；
* 四级压缩；
* File Buffer；
* Recall。

## `tests/sandbox/`

测试：

* Docker 启动；
* READY 检查；
* 只读挂载；
* 网络隔离；
* 命令超时；
* 资源限制；
* 容器清理。

## `tests/llm/`

测试：

* Provider Registry；
* Model Router；
* Tool Schema 转换；
* Mock Provider；
* Retry；
* Usage。

## `tests/tools/`

测试：

* Tool Registry；
* Validator；
* Policy；
* Executor Router；
* 路径穿越；
* Reviewer 权限。

## `tests/integration/`

测试：

* MCP；
* Pending Messages；
* Callback；
* FileStore；
* Blackboard；
* Failure Ledger。

## `tests/end_to_end/`

测试完整流程：

```text
创建任务
→ 调度
→ 创建沙箱
→ Agent调用工具
→ 生成报告
→ 验证
→ 保存文件
→ 清理资源
```

---

# 二十九、根目录文件

## `demo.py`

提供可直接运行的演示任务。

## `requirements.txt`

记录第一版实际依赖。

## `.env.example`

只记录环境变量名称，不含真实密钥。

## `.gitignore`

忽略密钥、缓存、工作空间、日志和本地数据库。

## `README.md`

说明：

* 项目目标；
* 架构；
* 运行方法；
* 演示任务；
* 目录；
* 安全机制；
* 多 Agent；
* 上下文压缩；
* 当前限制；
* 后续扩展。

---

# 三十、完整运行流程

## 阶段一：启动系统

```text
加载Settings
→ 创建Stores
→ 创建FileStore
→ 创建SandboxService
→ 注册模型
→ 注册工具
→ 初始化MCP
→ 创建Agent Runners
→ 启动Workers
→ 启动API
```

---

## 阶段二：接收任务

```text
API接收任务
→ 创建Task
→ 创建Conversation
→ 保存用户消息
→ Task进入Scheduler
```

---

## 阶段三：任务调度

```text
Scheduler检查并发与资源
→ Worker领取任务
→ 获取Execution Lease
```

---

## 阶段四：准备执行环境

```text
WorkspaceManager创建目录
→ RepositoryPreparer拉取仓库
→ ImageManager选择镜像
→ SandboxService启动容器
→ Healthcheck
→ Sandbox READY
```

---

## 阶段五：任务分类

```text
TaskClassifier
→ TaskProfile
→ ExecutionRouter
→ SINGLE / SEQUENTIAL / SYNC
```

---

## 阶段六：Agent 执行

Single：

```text
Global Context
→ AgentLoop
```

Sequential：

```text
Explorer
→ Developer
→ Reviewer
```

Sync：

```text
Manager
→ PhaseRouter
→ Delegation
→ 指定Agent
→ Blackboard
→ Manager重新决策
```

---

## 阶段七：工具调用

```text
ModelToolCall
→ Validator
→ Policy
→ ExecutorRouter
→ Sandbox或MCP
→ ToolResult
```

---

## 阶段八：错误处理

```text
ToolResult
→ Failure Detectors
→ Failure Ledger
→ Developer修复
或Reviewer Debug
或阶段回退
或Circuit Breaker
```

---

## 阶段九：上下文压缩

```text
Context Budget
→ NORMAL / LIGHT / MEDIUM / HEAVY
→ 大型内容卸载到FileStore
→ Context保留摘要与引用
```

---

## 阶段十：完成与验证

```text
Agent声明完成
→ Verifier独立验证
→ 通过则保存Artifact
→ 失败则返回修复反馈
```

---

## 阶段十一：通知与清理

```text
保存TaskResult
→ 写入Event
→ Pending Messages通知前端
→ Event Callback通知外部系统
→ 删除Sandbox
→ 清理Workspace
→ 释放Execution Lease
```

---

# 三十一、四个重点最终对应关系

## Agent 编排与调度

核心文件：

```text
task_scheduler.py
task_worker.py
execution_lease.py
task_orchestrator.py
task_classifier.py
execution_router.py
phase_router.py
agent_loop.py
runners/*
multi_agent/*
failures/*
reviewer_debug/*
```

## 沙箱与隔离执行

核心文件：

```text
sandbox/models.py
sandbox/capabilities.py
sandbox/policy.py
sandbox/service.py
sandbox/healthcheck.py
sandbox/image_manager.py
sandbox/providers/docker.py
```

## LLM 集成与工具调用

核心文件：

```text
llm/*
tools/*
integrations/mcp/*
context/*
```

## 整体架构与可扩展性

核心机制：

```text
Bootstrap依赖注入
Provider模式
Registry模式
Runner模式
Executor模式
统一领域模型
控制平面与执行平面分离
可靠事件与消息
可替换存储和沙箱
结构化可观测性
```

---

# 三十二、第一版实现顺序

## 第一阶段

```text
AgentLoop
SingleAgentRunner
ModelProvider
MockProvider
ToolRegistry
ToolValidator
ToolPolicy
NativeExecutor
```

## 第二阶段

```text
WorkspaceManager
RepositoryPreparer
SandboxService
DockerSandboxService
SandboxPolicy
Healthcheck
```

## 第三阶段

```text
TaskScheduler
TaskWorker
TaskOrchestrator
TaskStateMachine
ExecutionLease
```

## 第四阶段

```text
TaskClassifier
ExecutionRouter
TaskPhase
SequentialRunner
```

## 第五阶段

```text
Typed Blackboard
Explorer
Developer
Reviewer
Failure Ledger
```

## 第六阶段

```text
Reviewer Debug Mode
Circuit Breaker
```

## 第七阶段

```text
Context Lane
Light压缩
Medium压缩
File Buffer
Recall
```

## 第八阶段

```text
Sync Multi-Agent
Heavy压缩
Recovery
Kubernetes
Firecracker
```

---

# 三十三、项目最终定位

该项目不是简单地调用一次 LLM，也不是把四个 Agent 放在一起互相聊天。

它的核心是：

```text
平台级任务调度
+
任务级生命周期编排
+
最小Agent工具循环
+
结构化多Agent协调
+
独立角色上下文
+
统一错误闭环
+
安全沙箱执行
+
可替换模型和基础设施
```

最终形成：

```text
TaskScheduler
负责跨任务调度

TaskOrchestrator
负责单任务生命周期

ExecutionRouter
负责选择执行模式

Manager
负责单任务内部角色协调

AgentLoop
负责LLM与工具的最小循环

Blackboard
负责多Agent共享状态

Context Lane
负责各Agent独立上下文

Failure Ledger
负责错误检测与修复闭环

SandboxService
负责隔离执行

ModelProvider
负责模型适配

ToolExecutor
负责受控工具执行

Verifier
负责最终结果确认
```

这样能够让平台在不依赖单次巨大 Prompt 的情况下，通过角色分工、状态持久化、上下文压缩和安全执行环境，持续完成研究、实现、测试、审查和修复任务。
