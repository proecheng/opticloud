---
story_key: m2-0-saga-spike
epic_num: 0
story_num: M2.0
epic_name: Foundation
status: done
priority: 🔴 Critical (N5 unlock node 前置 — 砍 M2.1/M2.2/5.A.0 串行依赖)
sizing: M-L (3-5 hours; D1 fix — 7 tasks × 3-5 subtasks 实测；ADR + spike code)
type: architectural-spike
created_by: bmad-create-story
created_at: 2026-05-18
sources:
  - _bmad-output/planning/epics.md (Story M2.0 — RE6 fix)
  - _bmad-output/planning/architecture.md v2.2 (Concern #13 Distributed Billing Transaction / P33 Outbox / P56 Outbox Relayer Sidecar / C12 Outbox Relayer 独立 service)
  - _bmad-output/planning/prd.md v1.1 (NFR-R4 计费对账误差 = 0)
  - apps/auth-service/src/auth_service/models.py (existing outbox table reference)
  - infra/local-init/01-schema.sql (outbox table schema)
dependencies:
  upstream:
    - 0-1-monorepo-scaffold (done)
    - 0-2-docker-compose (done)
    - 0-5b-property-test-framework (done) — Hypothesis strategies usable
  downstream:
    - m2-1-outbox-relayer       — depends on Outbox decision
    - m2-2a-billing-critical-tests — depends on Saga state machine spec
    - 5-a-0a-saga-state-diagram — depends on Saga orchestration choice
    - 5-a-0b-saga-contract-fixtures — depends on Saga interface
    - 5-a-0c-saga-cross-epic-dryrun — depends on owner committee signoff
---

# Story M2.0: Saga + Outbox Architectural Spike

Status: **ready-for-dev**

## Story

As an **Architect**,
I want **2-3 hour focused spike documenting Saga (Orchestration vs Choreography) + Outbox Relayer (in-process / sidecar / separate service) decisions with rationale + sample code skeleton**,
so that **M2.1 (Outbox sidecar) / M2.2a (Billing 50 critical) / 5.A.0a/b/c (Saga 设计) 不再 串行 blocked，3 个 owner（Billing Lead / Solver Lead / SRE）有 sign-off-able 决策文档**.

## Acceptance Criteria

1. **AC1 — ADR (Architecture Decision Record) file — Nygard simplified template (R1-1)**：
   - 新增 `docs/adr/0001-saga-pattern.md`（Saga 选 Orchestration / Choreography / Hybrid + 选型理由）
   - 新增 `docs/adr/0002-outbox-relayer-deployment.md`（Outbox in-process / sidecar / separate service + 选型）
   - 每 ADR 含 6 sections (Nygard simplified)：
     1. **Context** — 业务/技术约束 + 触发本决策的问题
     2. **Decision** — 选定方案 + 1-line 原因
     3. **Status** — proposed / accepted / superseded（本 spike 输出 = accepted）
     4. **Consequences** — Positive / Negative / Mitigations 三栏
     5. **Alternatives Considered** — 决策矩阵表格
     6. **References** — 关联 Architecture v2.2 / PRD / 下游 stories

2. **AC2 — 决策矩阵清晰**：
   - ADR-0001 含 Orchestration vs Choreography 对比表（≥6 维度：可观测性 / 调试难度 / 状态机集中度 / 失败处理 / 跨服务变更成本 / **重试 + DLQ 策略 (A1 fix)**）
   - ADR-0002 含 in-process / sidecar / separate service 对比表（≥6 维度：故障隔离 / 资源开销 / 部署复杂度 / 一致性 / 演进路径 / **poll 频率 + schema migration 兼容性 (A3 + P1 fix)**）
   - 每维度有 1-2 句话评分理由（不只 ✅/❌）

3. **AC3 — 与 Architecture v2.2 一致性**：
   - 决策与 Architecture **P33 Outbox / P56 Outbox Relayer Sidecar / C12 Outbox Relayer 独立 service** 一致或显式说明 deviation
   - Concern #13 Distributed Billing Transaction 关键约束在 ADR 引用
   - 与 PRD v1.1 NFR-R4「计费对账误差 = 0」吻合
   - **ADR-0002 必含 "sidecar 实施技术选型" (R1-2 fix)** — 列出 ≥3 候选（Dramatiq actor / Cron loop / Debezium / Custom Python loop）+ 选择 + 理由

4. **AC4 — Saga 状态机 spec（不实施，只 spec）**：
   - 7 状态名 + transition 表：`pending → reserved → charged → completed`（+ `failed` / `refunded` / `rolled_back` 终态）
   - 每 transition 含触发条件 + 补偿动作 + 错误处理 + **超时阈值 (A2 fix)** + **重试策略 (A1 fix — exp backoff / max retries / DLQ)** + **transition cost annotation (P2 fix — 预估延迟 ms)**
   - 5.A.0a 实施 story 可直接照 spec 写代码
   - **R1-3 fix — Hybrid Saga 划分清单**：明示哪些事件用 Orchestration vs Choreography（≥3 例子，e.g. `billing.charge` → Orch / `audit.log.write` → Choreo / `notification.email.send` → Choreo）

5. **AC5 — Sample code skeleton (POC, ~120-150 行 — D2 fix)**：
   - 新增 `packages/shared-py/opticloud_shared/saga/__init__.py`（占位）
   - 新增 `packages/shared-py/opticloud_shared/saga/state_machine.py`（State enum + Transition class skeleton，含 docstring 引 ADR-0001 + **extension guide (U1 fix)**）
   - 不实施完整逻辑，仅 type signatures + transition matrix + **≥4 Hypothesis property tests** 证明状态机 invariants（Q1 + R1-6 fix）：
     1. 任意 valid transition 序列后状态属于 `State` enum（no dangling state）
     2. `refunded` / `rolled_back` 后退款金额 ≤ 原始扣费金额
     3. 终态（`completed` / `failed` / `refunded` / `rolled_back`）不能再 transition（terminal invariant）
     4. **idempotency invariant (Q1)**：相同 idempotency_key + 相同 amount 输入 → 相同 final state
   - 复用 Story 0.5b `monetary_amounts` + `uuids` strategies

6. **AC6 — 3 owner sign-off list**：
   - ADR-0001 + ADR-0002 末尾各含 sign-off section
   - 3 owners：Billing Lead / Solver Lead / SRE — 状态先 "pending" (Sprint 0 团队尚未组建)
   - 注：用户先前已声明 M0 不操心团队任命，sign-off 占位即可 / **不阻塞本 story 完成 (R1-5 fix)**
   - 但 **v1.5 商用前必须 3 签字** —— ADR-0001/0002 显式标注该 deadline

7. **AC7 — 引用关联 stories**：
   - ADR-0001 引 5.A.0a/b/c（实施 stories）+ M2.2a (Billing tests)
   - ADR-0002 引 M2.1 (Outbox sidecar 实施 story) + C12 + C9 (TDE)

8. **AC8 — README ADR index (U2 fix)**：
   - `docs/adr/README.md` 索引页含：
     - ADR-0001 + 0002 简介 + status
     - 两者关系（Saga 决策影响 Outbox event schema）
     - 后续 ADR 编号规则（连续递增）
     - 何时写 ADR（任何架构选型需要 cross-team 一致 / 不可轻易回滚）

9. **AC9 — Security & test guidance (S1 + Q2 fix)**：
   - ADR-0001 含 "Security: Saga state PII redaction in audit_log" — 描述如何处理金额等敏感字段
   - ADR-0001 含 "How to test" section — 列 M2.2a 测试覆盖建议（Hypothesis + scenarios）

10. **AC10 — Cross-namespace traffic guidance (S2 fix)**：
   - ADR-0002 含 "Network: cross-namespace traffic" — 描述 sidecar 与 Outbox table（prod-core）+ Redis broker（prod-data 还是 prod-core？）的流向 + P60 单向流策略验证

## Tasks / Subtasks

- [ ] **Task 1 (AC1, AC3) — ADR-0001 Saga 选型**
  - [ ] 1.1 创建 `docs/adr/` 目录
  - [ ] 1.2 写 ADR-0001 — Context / Decision / Consequences / Alternatives
  - [ ] 1.3 验证与 Architecture v2.2 Concern #13 一致

- [ ] **Task 2 (AC1, AC2, AC3) — ADR-0002 Outbox Relayer Deployment**
  - [ ] 2.1 写 ADR-0002 — 3 options 对比 + 选型
  - [ ] 2.2 验证与 P33 + P56 + C12 一致
  - [ ] 2.3 含演进路径（M2 sidecar → v2 单独 service）

- [ ] **Task 3 (AC4) — Saga 状态机 spec**
  - [ ] 3.1 列举 **7 states** (R1-4 fix)：`pending` / `reserved` / `charged` / `completed` / `failed` / `refunded` / `rolled_back`
  - [ ] 3.2 transition matrix 文档化（≥8 transitions）
  - [ ] 3.3 每 transition 含触发 / 补偿 / 错误处理
  - [ ] 3.4 状态机 invariant 列表（≥3 项）+ Hybrid Saga 划分清单 ≥3 例子 (R1-3)

- [ ] **Task 4 (AC5) — POC code skeleton**
  - [ ] 4.1 创建 `packages/shared-py/opticloud_shared/saga/__init__.py`
  - [ ] 4.2 写 `state_machine.py` — State enum (7 values) + Transition class + TRANSITIONS matrix
  - [ ] 4.3 写 `packages/shared-py/tests/test_saga_state_machine.py` — **≥3 Hypothesis property tests** (R1-6)
  - [ ] 4.4 跑 `uv run pytest packages/shared-py/tests/test_saga_state_machine.py -v` 通过

- [ ] **Task 5 (AC6, AC7) — Sign-off + 引用**
  - [ ] 5.1 sign-off section 占位（3 owners pending）
  - [ ] 5.2 cross-link 下游 stories

- [ ] **Task 6 (AC8) — ADR Index README (U2 fix)**
  - [ ] 6.1 写 `docs/adr/README.md` 含 2 ADR 简介 + 关系图 + 编号规则

- [ ] **Task 7 (AC9, AC10) — Security + Test + Network guidance (S1 + Q2 + S2 fix)**
  - [ ] 7.1 ADR-0001 加 "Security: state PII redaction" section
  - [ ] 7.2 ADR-0001 加 "How to test" section（与 M2.2a 联动）
  - [ ] 7.3 ADR-0002 加 "Network: cross-namespace traffic" + P60 验证

## Dev Notes

### 为什么 RE6 加这个 spike

Reverse Engineering 2 Round 发现 N5 unlock node 是高风险串行：
- Story 5.A.0 Saga 设计依赖 owner 决定 orchestration vs choreography
- Story M2.1 Outbox sidecar 实施依赖 deployment 模式选择
- Story M2.2a Billing tests 依赖 Saga 状态机 spec

如果 Sprint 0 W6 才决定 → 3 story 后续都得改 — **2 day spike 提前砍依赖**。

### Architecture v2.2 已有的相关 Pattern / Constraint（不要重复发明）

| Ref | 说明 | 本 spike 关系 |
|---|---|---|
| **Concern #13** | Distributed Billing Transaction（双写 + 幂等 + 退款） | 本 spike 主题 |
| **P33** | Outbox Pattern（事务一致性双写）| ADR-0002 必引 |
| **P56** | Outbox Relayer Sidecar（业务 service 内同进程跑 relayer） | ADR-0002 必引 + 评估 |
| **C12** | Outbox Relayer 独立 service（不混业务 Dramatiq actor） | ADR-0002 必引 + 评估 |
| **B2** | M1 fire-and-forget pub/sub；M2+ outbox sidecar | ADR-0002 演进路径基础 |
| **P63** | Event Versioning（dual publish + N=3 月） | Saga 内事件 schema 参考 |
| **C9** | TDE 全环境启用 + CI Vault dev mode | ADR-0002 安全考量 |

### Saga 选型快速分析（启发 ADR-0001）

**Orchestration（中心协调器）**：
- 一个 Saga Orchestrator 服务发命令到各 participant
- 优点：状态集中 / 易调试 / 易加新 step / 强 visibility
- 缺点：单点 / Orchestrator 本身需高可用
- 例：AWS Step Functions / Camunda / Temporal

**Choreography（事件驱动）**：
- 各 service 监听 + 反应 + 发新事件
- 优点：无单点 / loose coupling / 服务自主
- 缺点：状态分散 / 调试难 / 加 step 需改多服务
- 例：Kafka event chain

**Hybrid（本 spike 推荐方向）**：
- 关键状态机用 Orchestration（Billing Saga — 资金 critical）
- 非关键 fan-out 用 Choreography（audit log / notification）

### Outbox 部署 3 模式对比（启发 ADR-0002）

| 模式 | 部署 | 故障隔离 | 资源开销 | OptiCloud 适用阶段 |
|---|---|---|---|---|
| **In-process** | relayer 在业务 service 进程内跑 | 弱（business crash → 事件丢） | 最低 | M1 fire-and-forget 简陋版（B2） |
| **Sidecar** | 同 K8s pod 不同 container | 中（pod 共享 fate） | 中 | **M2+ 推荐（P56 + C12 折中）** |
| **Separate service** | 独立 deployment + DB 拉取 | 强 | 高 | v2+ 演进 |

**C12 表面"独立 service"，但 P56 是 "sidecar"** —— 看似矛盾。实际上 C12 含义是「不混业务 Dramatiq actor」（业务 service 不当 message broker），sidecar 仍符合 C12（不同 container 同 pod，独立进程）。

### Saga 状态机预 spec（Task 3 详化）

```
States: pending → reserved → charged → completed
       ↓        ↓          ↓
    failed   refunded   rolled_back
```

| Transition | 触发 | 动作 | 失败补偿 |
|---|---|---|---|
| `pending → reserved` | API 调用 + idempotency_key 解析 | Insert credit_transaction(status=reserved) + check balance | Set status=failed |
| `reserved → charged` | Service 调用成功 | Update status=charged + insert audit_log | refund → reserved (auto retry) |
| `charged → completed` | Outbox event 发出成功 | Update status=completed | retry outbox |
| `reserved → refunded` | 用户 cancel | Insert refund_transaction(amount=full) | log warning |
| `charged → rolled_back` | Service result rejected | Insert refund_transaction(amount=full) + audit | escalate to ops |

### Project Structure Notes

```
opticloud/
├── _bmad-output/
│   ├── adr/                                ← 本 story 新增
│   │   ├── README.md                       (ADR index)
│   │   ├── 0001-saga-pattern.md
│   │   └── 0002-outbox-relayer-deployment.md
│   ├── planning/                           (existing)
│   └── stories/                            (existing)
├── packages/shared-py/
│   ├── opticloud_shared/
│   │   ├── property_test_base/             (Story 0.5b)
│   │   └── saga/                           ← 本 story 新增
│   │       ├── __init__.py
│   │       └── state_machine.py
│   └── tests/
│       └── test_saga_state_machine.py         ← 本 story 新增
```

### 与下游 stories 接口契约

5.A.0a 实施 story 将 import：
```python
from opticloud_shared.saga.state_machine import State, Transition, TRANSITIONS
```

不要在本 spike 实施完整逻辑 —— **只定 interface + matrix**。具体业务 wiring（DB op / outbox emit）在 5.A.0/M2.1/M2.2a 实施时做。

### Reading order for reviewers

1. ADR-0001 (Saga choice)
2. ADR-0002 (Outbox deployment)
3. state_machine.py (skeleton — confirm interface stable)
4. test_saga_state_machine.py (1 property test — 证明 transition matrix consistent)

### Testing Standards

- 不需要业务实施测试（不在本 spike scope）
- 仅 1 Hypothesis property test：「从 pending 出发任意 transition 序列后状态必属于 enum」(无 dangling state)
- 用 Story 0.5b 提供 strategies (uuids, monetary_amounts)

### References

- [Source: epics.md Story M2.0 RE6 fix]
- [Source: architecture.md v2.2 Concern #13 + P33 + P56 + C12 + B2 + P63]
- [Source: prd.md v1.1 NFR-R4 计费对账误差 = 0]
- [Source: infra/local-init/01-schema.sql `outbox` table — 既有 schema 引用]

## Dev Agent Record

### Agent Model Used

(populated by /bmad-dev-story)

### Debug Log References

### Completion Notes List

### File List

预计新增（5 files）：
- `docs/adr/README.md`
- `docs/adr/0001-saga-pattern.md`
- `docs/adr/0002-outbox-relayer-deployment.md`
- `packages/shared-py/opticloud_shared/saga/__init__.py`
- `packages/shared-py/opticloud_shared/saga/state_machine.py`
- `packages/shared-py/tests/test_saga_state_machine.py`

预计修改：
- `_bmad-output/stories/sprint-status.yaml` (status: done)

## Validated Outcome

跑通验证命令：

```bash
# 1. ADR 文件存在 + 含必要 sections
ls -la docs/adr/
test -s docs/adr/0001-saga-pattern.md
test -s docs/adr/0002-outbox-relayer-deployment.md
grep -E "^## (Context|Decision|Consequences|Alternatives)" docs/adr/0001-saga-pattern.md

# 2. Saga code skeleton imports OK
PYTHONPATH=packages/shared-py uv run python -c "from opticloud_shared.saga.state_machine import State, Transition, TRANSITIONS; print(f'states={len(State)} transitions={len(TRANSITIONS)}')"

# 3. Property test 通过
uv run pytest packages/shared-py/tests/test_saga_state_machine.py -v
# 期望 exit 0 + 1+ passed

# 4. 与 architecture v2.2 一致性
grep -E "(P33|P56|C12|Concern #13)" docs/adr/0001-saga-pattern.md docs/adr/0002-outbox-relayer-deployment.md
```

## Definition of Done

- [ ] All 5 tasks marked complete
- [ ] 7 ACs satisfied
- [ ] ADR-0001 + ADR-0002 文件含 5 mandatory sections each
- [ ] Decision matrix ≥5 维度（each ADR）
- [ ] Saga state machine skeleton 可 import
- [ ] 1+ property test pass (Hypothesis)
- [ ] 与 Architecture v2.2 ref 一致（grep 验证）
- [ ] sign-off section 3 owners 占位（pending OK）
- [ ] No regressions
