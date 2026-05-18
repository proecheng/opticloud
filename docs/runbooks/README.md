# OptiCloud Runbooks

> **Owner**：DevOps / SRE 团队（标准档；精简档 = 课题组创始人 + 学生兼职）
> **Status**：🚧 骨架 / Skeleton（M0-M5 期间填充）
> **关联架构**：`_bmad-output/planning/architecture.md` Appendix D / Gap G18
> **Last Updated**：2026-05-17

---

## 📋 用途

Day-2 Operations Runbooks — 应急响应 + 例行运维 + 容灾演练 SOP。每个 runbook **必须独立可执行**（新 oncall 拿到即可操作）。

---

## 🚀 Sprint 0 Kick-off SOP（M0 Day 1 必读）

### 0. Sprint 0 Day 1 Kick-off — Cross-Epic Owner Committee 任命

- 📄 **`runbooks/sprint-0-kickoff.md`** ✅ **READY**
- 🎯 用途：Sprint 0 启动当天 4 小时 Kick-off SOP — 8-role Cross-Epic Owner Committee 任命 + 5 unlock node + J1 4 锚点 + Calibration Week + 4 M0 wk1 必启动 stories
- 🎯 输出：8 Owner Commitment Letters / Linear labels / team-contacts.md / cadence calibration baseline / Day 1 Status update
- 🎯 触发：M0 Sprint 0 Day 1（用户确认 / 团队组建完成时）

---

## 🚨 Critical SOPs（M3 末必须 ready）

### 1. Backup Restoration Runbook

#### 1.1 Postgres 备份恢复 SOP（精简档 + 标准档）

- 📄 **`runbooks/backup-restore-postgres.md`**
- 🎯 内容：
  - **场景 A**：单库 corruption / 数据误删 → point-in-time recovery（PITR）从 WAL 恢复
  - **场景 B**：实例完全丢失 → 阿里云 RDS 快照恢复 + 跨区备份验证
  - **场景 C**：跨 region 灾难（区域级故障）→ AWS S3 跨云备份恢复
- 🎯 步骤模板：
  ```
  1. 确认丢失数据范围 + 时间点
  2. 停止接受写入（api-gateway 503）
  3. 检查最近备份点（每日全量 + WAL 持续）
  4. 阿里云 RDS Console / CLI 恢复到目标时间点
  5. 验证数据完整性（checksums + key tables count）
  6. 灰度切流（5% → 50% → 100%）
  7. Postmortem（P0 触发 → 24h 公开）
  ```
- 🎯 **季度演练**：每季度 1 次完整恢复演练（在 staging 环境），生成验证报告

#### 1.2 Vault Secret 恢复 SOP

- 📄 **`runbooks/backup-restore-vault.md`**

#### 1.3 S3 / OSS 对象恢复 SOP

- 📄 **`runbooks/backup-restore-storage.md`**

#### 1.4 Image / Repro 5y 归档恢复 SOP（与 G7 联动）

- 📄 **`runbooks/repro-image-restore.md`**

---

### 2. On-Call Rotation Policy

#### 2.1 精简档 On-Call（1-2 人）

- 📄 **`runbooks/oncall-policy-lite.md`**
- 🎯 内容：
  - **Tier 1**（all hours）：创始人 + 1 学生兼职轮替
  - **告警分类**：
    - P0（24h Postmortem 触发）：服务全停 / 数据丢失 / 沙箱泄漏 / 资金账本错 → 立即 page
    - P1（next business day）：单 service degrade / SLA 违约 → 站内 ticket
    - P2（weekly review）：监控数据异常但未触发用户感知 → 周会复盘
  - **响应 SLA**：P0 15 min 接告警 / P1 4h 工作时间响应
  - **Escalation**：30 min 无应答 → 升级到课题组所有成员

#### 2.2 标准档 On-Call（5 人全职 + 2 backup）

- 📄 **`runbooks/oncall-policy-standard.md`**
- 🎯 内容：
  - **Tier 1**：DevOps 工程师轮值（1 周 1 轮）+ PagerDuty / 钉钉机器人
  - **Tier 2**：技术 lead（escalation）
  - **Tier 3**：CTO / 创始人（最高级紧急）
  - **休假覆盖**：必有 backup（不允许单人覆盖）
  - **Compensation**：On-call 补贴（M3+ 启动）

---

### 3. Alert Threshold Catalog

- 📄 **`runbooks/alert-thresholds.yaml`**
- 🎯 内容（按 service × metric 列举）：

```yaml
api-gateway:
  cpu_percent:
    warning: 70 (> 5min)
    critical: 90 (> 2min)
  memory_percent:
    warning: 75
    critical: 90
  latency_p95_ms:
    warning: 300
    critical: 500
  error_rate_percent:
    warning: 1
    critical: 5
  rate_limit_429_rate:
    warning: 10 (per minute)
    critical: 100 (per minute)

solver-orchestrator:
  pending_queue_depth:
    warning: 50
    critical: 200
  solve_failure_rate:
    warning: 5%
    critical: 15%

chat-service:
  first_token_p95_ms:
    warning: 2000
    critical: 4000
  sse_connection_count:
    warning: 40
    critical: 80
  aigc_filter_block_rate:
    info: > 1%（log only）
    warning: > 5%
    critical: > 15%（可能 prompt injection 攻击）

# ... 其他 services
```

---

### 4. 容灾演练 SOP（季度 1 次）

- 📄 **`runbooks/dr-drill-quarterly.md`**
- 🎯 内容：
  - 季度演练 checklist（数据库恢复 / Vault 密钥恢复 / 跨区故障切换 / Provider 退出迁移）
  - 演练报告模板
  - 演练失败项 → ADR 触发改进

---

## 🟠 Important SOPs（M5 商用前 ready）

### 5. P0 Incident Response 24h Postmortem 模板

- 📄 **`runbooks/postmortem-template.md`**
- 🎯 内容：标准 5 段（What happened / Timeline / Root cause / Impact / Action items）+ 24h 公开发布流程（Hard Rule #6）

### 6. AIGC 巡查应急 Runbook（FR Journey 8 配套）

- 📄 **`runbooks/aigc-inspection-response.md`**
- 🎯 内容：
  - 网信办通知 → 4h 召集合规团队
  - 涉嫌 sample 导出 + 自查
  - Critic prompt 加强 / 敏感词二级过滤 / SKU 暂停 2 周复核
  - 24h 内 status 公告 + 整改报告

### 7. Sandbox 越权事件响应（R8 配套）

- 📄 **`runbooks/sandbox-breach-response.md`**
- 🎯 内容：
  - **立即**：暂停 sandbox-runner service（所有 chat 转 fallback / 退款 Credits + 20%）
  - **24h 内**：root cause 调查 + Postmortem 发布
  - **48h 内**：补丁 + 红队验证 + 恢复服务

### 8. 计费对账误差应急（B12 配套）

- 📄 **`runbooks/billing-mismatch-response.md`**
- 🎯 内容：双写账本扫差脚本 + 误差 > 1 cent 触发应急 + 用户补偿流程

### 9. Provider 退出 30 day 预通知 SOP（R7 + Repro 5y 联动）

- 📄 **`runbooks/provider-exit-handling.md`**

### 10. Critic 误判事件响应

- 📄 **`runbooks/critic-misjudgment-response.md`**

---

## 🟡 Routine Maintenance SOPs

### 11. 密钥轮换日历（C10 配套）

- 📄 **`runbooks/key-rotation-calendar.md`**
- 🎯 内容：

| 密钥类型 | 轮换周期 | 责任人 | SOP 链接 |
|---|---|---|---|
| JWT 签名密钥 | 月度 | DevOps | jwt-rotation.md |
| API Key（用户）| 用户自管 + 异常地理触发 | Auth-Service | — |
| DB 密码 | 季度 | DevOps | db-password-rotation.md |
| Vault Root Token | 半年 | 创始人 + DevOps | vault-root-rotation.md |
| Stripe Webhook Secret | 半年 | DevOps | stripe-webhook-rotation.md |
| Argon2 Pepper（Vault）| 年度 | DevOps + 创始人 | pepper-rotation.md |

### 12. Sandbox GC + 资源清理

- 📄 **`runbooks/sandbox-gc.md`**
- 🎯 内容：每日清理 90s 强杀后残留 gVisor 容器 + emptyDir + 临时文件

### 13. 日志保留分级 + 归档 SOP

- 📄 **`runbooks/log-retention.md`**
- 🎯 内容：

| 日志类型 | 保留期 | 归档路径 |
|---|---|---|
| Debug 日志 | 24h | 自动滚动 |
| INFO 业务日志 | 30 day | Loki + S3 冷归档 |
| WARN / ERROR 日志 | 90 day | Loki + S3 |
| **Audit Log（FR O3）**| **7 year** | dedicated `audit_log` 表 + 跨年 S3 Glacier |
| Postmortem | 永久 | docs/postmortems/ |
| 合规审计 trail | 7 year + AIGC trace | 同 audit |

### 14. 容量自动扩缩 Runbook

- 📄 **`runbooks/autoscaling.md`**
- 🎯 精简档：ECS 手动升配 trigger（CPU 持续 > 80% 30min）
- 🎯 标准档：K8s HPA + KEDA + warm pool controller 触发参数

### 15. 成本异常告警 SOP

- 📄 **`runbooks/cost-anomaly.md`**
- 🎯 内容：阿里云账单 API 接入 → 月费 +50% 自动告警 → 排查清单（DDoS / LLM 滥用 / sandbox 资源泄漏 / GPU 闲置率）

---

## 📅 实施 Timeline

| 阶段 | 必须完成 | 涵盖 |
|---|---|---|
| **M0-M1** | None（DevOps 还在 ramp up）| — |
| **M3 末** | SOP 1-4（Backup / On-Call / Alerts / DR Drill）| G18 critical |
| **M5 商用前** | SOP 5-10（Incident / AIGC / Sandbox / Billing / Provider / Critic）| Important |
| **M5+ 持续** | SOP 11-15（密钥 / GC / 日志 / 扩缩 / 成本）| Routine |

---

## 🤝 责任清单

| 角色 | 责任 |
|---|---|
| **DevOps / SRE 工程师** | 各 SOP 维护 + 演练执行 + on-call 主力 |
| **创始人 / CTO** | P0 incident 决策 + Postmortem 审稿 |
| **课题组成员** | Critic 误判 / AIGC 巡查 时担任内容专家 |
| **法务律师** | AIGC 巡查 / 数据合规事件法务支持 |

---

## 🔗 关联文档

- 架构 SOP 锚点：`_bmad-output/planning/architecture.md` § P29-P32 / P38 / P43 / P46 / P59 / P60
- ADR 应急决策：`docs/adr/`
- 法务流程：`docs/legal-templates.md`
- 历史 Postmortem：`docs/postmortems/`（按日期归档）
