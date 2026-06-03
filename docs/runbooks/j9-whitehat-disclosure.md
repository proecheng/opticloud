# J9 白帽负责任披露 Dry-Run Runbook

Owner: Security
Status: Draft ready
Last updated: 2026-06-03

## 适用范围

本 runbook 用于演练和执行 J9 白帽负责任披露路径：从研究者发现 `/.well-known/security.txt`，到邮件 intake、48h 人工回执、CVSS 分级、修复、公开致谢/奖励人工交接、以及复盘证据归档。

当前版本是 static vertical slice 和 dry-run contract。它不表示 SMTP auto-reply、ticket automation、PGP encrypted intake、CVE tracking、bounty payment、Telegram/DingTalk bot 或 HackerOne-like platform integration 已在生产环境上线。

## 角色

| 角色 | 职责 |
|---|---|
| Security | 维护 `/security`、接收报告、回执、分级、协调披露、复盘归档 |
| Engineering | 评估影响面、修复漏洞、提供部署和回滚证据 |
| Legal/Finance | 处理奖励资格、反欺诈、税务/付款、公开致谢授权 |
| Support/Academic | 承接普通产品 bug 或学术/学生渠道 handoff |

## Stage 1: Discover

触发条件：研究者从公开 API、产品页面或账号流程发现潜在漏洞，并读取 `/.well-known/security.txt` 或 `/security`。

步骤：

1. 确认 `/.well-known/security.txt` 可访问，且包含 `Contact: mailto:security@opticloud.cn`、`Policy:`、`Canonical:`、`Preferred-Languages:` 和 `Expires:`。
2. 确认 `/security` 页面公开可访问，无登录、cookie、JWT、API key、浏览器 storage 或网络 fetch 依赖。
3. 确认页面仍说明普通产品 bug、学术/学生披露、国家/APT 类报告与负责安全披露不同。

Dry-run evidence：

- `security.txt` 响应快照。
- `/security` 页面渲染快照或测试输出。
- 无 `Encryption:` 字段的检查结果，除非真实 PGP key URL 已上线。

## Stage 2: Intake

触发条件：`security@opticloud.cn` 收到报告，报告声称影响 OptiCloud 公共 API、产品页面或账号流程。

步骤：

1. 记录收到时间、报告者联系方式、影响面、漏洞类型、PoC/复现步骤和 CVSS 估计。
2. 检查报告是否满足 required fields：affected surface、impact、reproduction or PoC、CVSS estimate、reporter contact。
3. 若是普通产品 bug，转 Support；若是学术/学生披露，转 Academic handoff；若是国家安全/APT 类事件，暂停普通产品流程并升级 Legal/Security 负责人。
4. 检查 safe-harbor 边界：最小证明、无客户数据外泄、无破坏性测试、无持久化、无社工、无 DDoS、优先合成或研究者自有数据。

Dry-run evidence：

- 脱敏报告摘要。
- required fields checklist。
- disclosure type routing decision。

## Stage 3: Acknowledge

触发条件：报告通过 intake，被判定为负责安全披露路径。

步骤：

1. Security 人工发送初始回执，目标是在收到报告后 48h 内完成。
2. 回执仅确认收到和后续协调方式，不承诺奖励、CVE、公开致谢或固定修复日期。
3. 若邮件收取失败，记录为 planned fallback 演练项；不得声明 PGP/key fallback 或内部 alert 自动化已经上线。
4. 记录手工 tracking reference，例如内部 issue、PR、或安全负责人日志条目。

Dry-run evidence：

- 回执时间戳。
- 手工 tracking reference。
- 邮件失败 fallback 的 planned/boundary 记录。

## Stage 4: Triage

触发条件：Security 确认报告可复现或需要 Engineering 协助复现。

步骤：

1. 按 CVSS、可利用性、数据暴露、权限边界、是否正在被利用进行分级。
2. 标记 `CVSS >= 7.0`、`CVSS 4-6.9`、低危或信息性报告。
3. 对国家/APT、供应链、凭据泄露、跨租户访问、资金账本风险单独升级。
4. 如报告重复，记录 first-disclosure 判断依据，但不要公开研究者信息。

Dry-run evidence：

- CVSS 评分理由。
- 影响面和复现结论。
- duplicate disclosure decision。

## Stage 5: Remediate

触发条件：Triage 确认需要代码、配置、密钥、数据、文档或流程修复。

步骤：

1. `CVSS >= 7.0` 进入高优先级 hotfix path；正在利用或平台关键路径风险可进入内部 24h hotfix 目标。
2. `CVSS 4-6.9` 进入 7d patch target。
3. Engineering 提供补丁 PR、测试、部署引用和回滚说明。
4. Security 复核 public-safe remediation summary，避免泄露 payload、内部拓扑、凭据或客户数据。

Dry-run evidence：

- Patch PR 或配置变更引用。
- 测试输出和部署引用。
- 回滚说明。
- public-safe remediation summary。

## Stage 6: Coordinate disclosure

触发条件：修复已部署或风险已通过缓解措施降到可披露状态。

步骤：

1. 与研究者协调披露窗口、公开 wording 和是否匿名。
2. 再次检查 duplicate handling 和 first-disclosure credit。
3. 若涉及第三方、供应链或潜在 CVE，只记录 manual coordination boundary；不得声明 CVE tracking automation active。
4. Legal 复核公开文字，特别是客户影响、个人信息、奖励和法律责任表述。

Dry-run evidence：

- 研究者沟通日志。
- 公开文字草稿。
- redaction review checklist。

## Stage 7: Acknowledge or reward

触发条件：披露协调完成，且研究者申请公开致谢或奖励资格评估。

步骤：

1. Security 准备公开致谢候选记录，默认不包含邮箱、账号 ID、客户数据或 payload。
2. Legal/Finance 人工评估奖励资格、反欺诈、付款、税务和重复披露争议。
3. 对重复报告发送感谢，不暗示奖励资格。
4. 页面和文档只能称为 manual/planned handoff，不得称 bounty payment automation active。

Dry-run evidence：

- 公开致谢授权记录。
- 奖励资格人工评估记录。
- duplicate thanks 记录。

## Stage 8: Retrospective evidence

触发条件：修复、协调、致谢/奖励 handoff 已结束，或报告被判定为无效/重复。

步骤：

1. 归档脱敏证据包：报告摘要、时间线、CVSS、修复引用、部署引用、沟通摘要、hardening checklist 更新。
2. 更新 J9 hardening checklist 中相关项的状态或 follow-up。
3. 记录哪些自动化仍未上线，避免后续页面或 runbook 过度宣称。
4. 如涉及 P0/P1 用户影响，按公开 status/postmortem 流程另行处理。

Dry-run evidence：

- Redacted evidence bundle。
- Lessons learned。
- hardening checklist update。

## Redaction Rules

必须移除或替换：

- 客户名称、邮箱、账号 ID、租户 ID、手机号、地址、账单信息。
- API key、JWT、session cookie、凭据、密钥、内部 token。
- 可直接利用的 raw exploit payload、未修复 endpoint 细节、内部 host/IP、数据库名。
- 第三方未公开漏洞细节和研究者不愿公开的身份信息。

允许保留：

- 公共路径级别影响面，例如 `/api/v1/*`。
- CVSS 分值和高层原因。
- 修复 PR、部署版本、测试命令、时间戳。
- 研究者明确授权的公开署名。

## Inactive Automation Boundaries

以下能力在本 story 中不是 active production automation：

- SMTP auto-reply 和 ticket automation。
- Telegram/DingTalk/PagerDuty bot。
- PGP encrypted intake 和 `security.txt` 的 `Encryption:` 字段。
- CVE assignment、CNA workflow 或 CVE tracking automation。
- Bounty payment、tax/invoice handling 和 reward payout automation。
- Public thanks page database。
- HackerOne-like platform integration。

任何页面、测试、runbook 或 release note 如出现上述 active claim，必须在合并前修正为 manual、planned、blocked、handoff 或 dry-run contract。
