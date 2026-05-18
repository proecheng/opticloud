# Sprint 0 Day 1 Kick-off SOP — Cross-Epic Owner Committee 任命

> **Owner**：PM + Founder
> **Status**：✅ READY FOR EXECUTION（M0 Sprint 0 Day 1）
> **Source**：Implementation Readiness Report v3 R-CI2 / Epics.md AE-1+2 RE1 fix
> **Last Updated**：2026-05-17
> **Trigger**：Sprint 0 启动当天上午（M0 W0 Day 1）

---

## 📋 用途

OptiCloud Sprint 0 启动前**必须执行**的 4 小时 Kick-off 会议 SOP，目标：
1. **任命 8 个 Cross-Epic Owner Committee roles**（防 Story 5.A.0 Saga 跨 Epic 死锁 / N5 unlock 卡住的根源 RE1）
2. **同步 5 unlock node 序列 + J1 Vertical Slice 4 锚点 deadlines**（W4-10）
3. **Calibration Week (Story 0.0) 3-day 启动 — 团队 cadence 实测**
4. **Auto-Degrade Health Check 周报机制启动**（每周末 unlock node 进度 review）

---

## 🕐 Agenda（4 小时）

### Block 1 (09:00-10:00) — Committee 任命（核心）

#### 8-Role Cross-Epic Owner Committee

| # | Role | Owns Epic / Stories | 候选 |
|:-:|---|---|---|
| **1** | **PM** | Sprint 0 overall + Cross-Epic coordination + R-CI1/2/3 跟踪 + Story M0.AIGC-status / M0.LEGAL-status weekly tracking | 课题组负责人 |
| **2** | **Architect** | Story M2.0 Spike + M3.4b AIGC Contract Test + M3.7 Sandbox Audit + M3.8 LLM Abstraction + M3.9 Image Archival | TBD（外招 / 课题组内）|
| **3** | **Billing Lead** | Epic 5.A (Credits + Charging + Saga) + Story 5.A.0a/b/c + M2.2a/b/c | TBD |
| **4** | **Solver Lead** | Epic 3 + Epic 4.B (Coder + Critic + Sandbox) + 调用 Saga 跨 Epic contract | 吕老师 / 课题组研究员 |
| **5** | **SRE / NFR-P Owner** | Story M3.6a/b/c/d/e (Chat 延迟 G6) + M2.3 G3 (Cost-attribution) + Cost-attribution 红线告警自动化 | TBD |
| **6** | **QA Lead** | Story 0.5b Property-Test + Story 0.13a/b Playwright E2E + M3.2 Contract Test + M2.2a-c Billing 一致性 | TBD |
| **7** | **Frontend Lead** | Story 0.9-0.12 + packages/ui Tier 1 12 v1 stubs + UX Component PR-gates + Storybook + a11y Hook | TBD |
| **8** | **NFR-COST Owner** | Epic 9 NFR Governance + cost_attribution ACL + 红线告警 + Cost Anomaly Detection | 财务 / PM 兼任 |

**+ 1 可选 Provider Interface Lead (SC9 fix)** — owns Epic 7.A 接口预留 v1 / v2 Epic 7.B 准备（如果有学者愿提前 ramp）

#### 任命输出（书面）

- 每 owner 签 **Sprint 0 Owner Commitment Letter**（含 deliverable + deadline + 联系方式）
- Linear / GitHub Project 创建 8 个 owner-tagged labels
- Owner 联系矩阵入 `docs/runbooks/team-contacts.md`（新增）
- **Day 1 Status update** 发 dingtalk / Slack 频道（含 8 owner 名单 + 各自第一周 milestone）

### Block 2 (10:00-11:00) — 5 Unlock Node Sequence Walkthrough

| Node | Story 集合 | Deadline | Owner |
|:-:|---|:-:|---|
| **N1** | 0.1 Monorepo + 0.2 docker-compose + 0.5 Pre-commit + 0.5b Hypothesis + 0.6 Auth | W0-3 | Frontend Lead + Backend Lead（PM 兼）|
| **N2** | 0.4 OpenAPI codegen + 0.7 Health/Readiness + 0.3 CI path-filter | W0-3 并行 | QA Lead + Backend Lead |
| **N4** | 0.8 Docker multi-stage + SBOM + image 签名 | W3-5 | Architect + SRE |
| **N3** | 0.9 packages/ui scaffold + Tier 1 12 stubs + 0.10 Tailwind+Brand tokens + 0.11 Storybook+Chromatic + 0.12 a11y Hook | **W5-10**（PMR1 + RE8 修订后）| Frontend Lead |
| **N5** | M2.0 Spike + 5.A.0a/b/c Saga 设计 + M2.2a Billing 50 critical + M2.1 Outbox | W6-10 | Architect + Billing Lead + QA Lead |

### Block 3 (11:00-12:00) — J1 Vertical Slice 4 锚点 deadlines + Health Check

#### J1 锚点表

| Epic | Story | Deadline | Owner |
|:-:|---|:-:|---|
| Epic 2 | **Story 2.1** — `GET /v1/algorithms` 公开免鉴权 | W4 | Backend Lead + Frontend Lead |
| Epic 1 | **Story 1.1a + 1.1b** — 注册 + API Key + Postman 一键导入 | W5 | Backend Lead + Frontend Lead |
| Epic 3 | **Story 3.1** — `POST /v1/optimizations` LP solve | W6 | Solver Lead + Backend Lead |
| Epic 5.A | **Story 5.A.1** — Credits 扣费 + balance Modal | W10 | Billing Lead + Frontend Lead |

#### Path B Health Check & Auto-Degrade

- **每周末 Health Check 周报**：unlock node 进度 (PM + Scrum Master 维护)
- **Auto-Degrade 触发**：
  - Week 4 N1+N2 完成度 < 60% → **Path B 自动降级 Path C**（仅 3 stories minimal Sprint 0）
  - Week 8 N3+N4 完成度 < 60% → packages/ui 简化为 Tier 1 Core 5
  - Week 10 N5 完成度 < 60% → Saga 简化版（仅 idempotency + outbox）
- **降级触发后 24h 内**：PM + Architect + Founder 三方决策会

### Block 4 (13:00-14:00) — Story 0.0 Calibration Week 启动

#### Calibration Week SOP（3 day）

**目标**：基于实际团队能力校准 cadence（Carson C3 默认 3-4 stories/week ≥3 人 / 2-3 day/story；实际可能不同）

| Day | Activity |
|:-:|---|
| **Day 1** | 团队 self-assessment：每 owner 估时 own first story（Sprint 0 N1+N2 stories）+ 比 baseline 标准档 cadence |
| **Day 2** | 实际起 Story 0.1 Monorepo 跑通 + 跟踪实际耗时 vs 估时 |
| **Day 3** | Calibration 输出：调整 Sprint 0 W0-10 timeline + 调整 M5 末预估 stories 数（实际 cadence × 22 周）+ 调整 J1 锚点 deadlines |

#### Calibration 输出

- `docs/runbooks/team-cadence-calibration.md`（新增）— 记录实测 velocity + 估时偏差
- 调整后的 J1 锚点 deadlines（如实际比 RE9 慢 2 周，全部 +2 weeks）
- Memory note 更新：实际 M5 末 stories 数（取代 65-80 default）

### Block 5 (14:00-15:00) — Critical Stories Day 1 启动

#### 4 个 M0 wk1 必启动 stories

| Story | Owner | Day 1 Action |
|:-:|---|---|
| **M0.LEGAL-1** EPL+ECOS+Apache 2.0 法务审定 deliverable 🔴 | 法务 + Founder | 联系法务事务所 + 准备 Apache 2.0 信源 + 学界合作合同模板 |
| **M0.LEGAL-status** 法务签字 + 中介费付款 weekly tracking | PM | Linear ticket 创建 + weekly cadence 锁定 |
| **M0.AIGC-status** AIGC 备案状态 weekly tracking 🔴 | PM | 联系 AIGC 备案中介 + 准备 ¥3-8 万付款 + 三级 fallback decision tree |
| **Story 0.1** Monorepo 骨架 | Frontend Lead + Backend Lead | git clone + pnpm-workspace.yaml 初稿 |

---

## ✅ Kick-off 完成 Checklist

- [ ] 8 个 Owner 任命书面确认（Commitment Letter 签字）
- [ ] Linear / GitHub Project 8 个 owner-tagged labels 创建
- [ ] `docs/runbooks/team-contacts.md` 联系矩阵入档
- [ ] 5 unlock node 序列 + deadlines + owners 全员清楚
- [ ] J1 Vertical Slice 4 锚点 deadlines + owners 全员清楚
- [ ] Path B Health Check + Auto-Degrade 规则全员清楚
- [ ] Story 0.0 Calibration Week 启动（Day 1）
- [ ] 4 M0 wk1 必启动 stories（M0.LEGAL-1 / M0.LEGAL-status / M0.AIGC-status / Story 0.1）有 owner 接手
- [ ] Day 1 Status update 发频道（含 8 owner 名单 + 第一周 milestone）

---

## 📞 紧急升级路径

| 情况 | 升级到 |
|---|---|
| Owner 任命冲突或缺岗 | Founder + PM 24h 内决策 |
| Calibration 显示 cadence 比标准档慢 30%+ | PM + Founder + Architect 三方决策 — 启动 Path C 降级 |
| Day 1 任一 critical story 受阻 | Owner 立即上报 PM；PM 24h 内决策 |
| 法务签字延期超 M0 wk2 | Founder 直接介入 + 中介费加急路径 |

---

## 🔗 关联文档

- 规划主文档：`_bmad-output/planning/epics.md`（21 Epics / 192 Stories）
- Readiness Report：`_bmad-output/planning/implementation-readiness-report-2026-05-17-v3.md`
- Architecture v2.2：`_bmad-output/planning/architecture.md`
- 团队联系：`docs/runbooks/team-contacts.md`（新建，本 SOP 输出）
- Cadence 校准：`docs/runbooks/team-cadence-calibration.md`（新建，Calibration Week 输出）
