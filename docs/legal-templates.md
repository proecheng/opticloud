# Legal Templates Index

> **Owner**：法务团队 + 课题组创始人
> **Status**：🚧 骨架 / Skeleton（M0-M5 期间填充）
> **关联架构**：`_bmad-output/planning/architecture.md` Appendix C / Gap G16 / G17 / Constraint C21
> **Last Updated**：2026-05-17

---

## 📋 用途

本文档是 OptiCloud 法律文档模板的**索引 + 责任清单**。每项模板独立维护为子文档（待法务起草）。**架构文档 + PRD 已覆盖技术合规；本文档覆盖商业 / 用户 / 合作 / IP 层面合规**。

---

## 🚨 紧急（M0 wk1-2 必须）

### 1. EPL / ECOS License SaaS 商用法务签字（C21 + G17 ★ Critical）

- 📄 **`docs/adr/0003-epl-ecos-license-decision.md`**（待签字）
- 🎯 内容：
  - EPL（IPOPT / Bonmin / Couenne）仅调用不 fork 在 SaaS 后端**可否商用**结论
  - ECOS GPLv3 v1 使用 vs SCS MIT 备用决策
  - SCIP 商业付费 vs 学术免费在 SaaS 后端的合规结论
- ⚖️ **签字方**：外聘法务律师（中国大陆 + 涉及开源许可的境内案例经验）
- 🚦 **未签字后果**：v1 SKU 退化（不上 EPL/ECOS/SCIP 等价物）→ R3 风险触发

---

## 🟠 M1 末必须（v1 上线 hard-gate）

### 2. 用户服务协议（EULA / Terms of Service / ToS）

- 📄 **`docs/legal/eula.md` + `eula.zh-CN.html` + `eula.en-US.html`**
- 🎯 关键条款：
  - **AI 生成内容免责**（NL Summary / Critic / 优化建议仅供参考，最终决策责任在用户）
  - **服务可用性**（v1 best-effort，v1.5 起分层 SLA）
  - **数据所有权**（用户输入 = 用户所有；输出 = 用户所有；元数据 = 平台所有）
  - **禁止用途**（违反 AIGC 规定 / 加密货币 / 非法活动）
  - **退款 / 终止条款**（FR B5 联动）
  - **争议解决 / 适用法律**（中国大陆法 / 仲裁机构）
- 📌 **触发实施**：用户注册必勾选确认（FR A1 配套）

### 3. 隐私政策（Privacy Policy）

- 📄 **`docs/legal/privacy-policy.md` + 双语 HTML**
- 🎯 关键条款（**PIPL 兼容**）：
  - 收集的数据类型（注册信息 / API 调用 / 输入数据 / 元数据）
  - 数据使用目的 + **法定基础**
  - 数据保留期（默认不进训练集 / 7 day 删除 / Audit 7 年）
  - **跨境传输条件**（仅用户主动选 N4 远程国际 LLM 时；同意书 + 数据出境评估）
  - 第三方数据共享（DeepSeek API / Stripe / 微信 / 支付宝 等）
  - 用户权利（PIPL §44-50：知情 / 删除 / 更正 / 拒绝自动化决策）
  - 14 岁以下不允许 + 14-18 监护人确认
- 📌 **触发实施**：用户注册必勾选确认

### 4. 数据处理协议（DPA / Data Processing Agreement）

- 📄 **`docs/legal/dpa-template.md`**
- 🎯 用途：B2B 客户（Team / Enterprise plan）签约时附加
- 关键条款：
  - 数据处理目的 + 范围
  - 安全措施（TLS 1.3 / TDE / Vault HSM / 沙箱）
  - 子处理者清单（DeepSeek / 阿里云 / AWS 等）
  - **数据 sub-processor 变更通知**（30 day 预通知）
  - 审计权利（客户每年 1 次审计 OR 接受 SOC 2 报告）

---

## 🟠 M5 商用前（hard-gate 触发）

### 5. NL Summary / Critic Agent 免责声明（弹窗 + 文档）

- 📄 **`docs/legal/ai-output-disclaimer.md`**
- 🎯 形式：
  - **每次 NL Summary 输出底部 footer**：「本回答由 AI 生成，仅供参考。最终决策请结合人工判断。如有疑问，请联系客服。」+ 不可见 zero-width Unicode 审计标识 + trace_id（G12 联动）
  - **Critic 置信度 < 0.6 时弹 Modal**：「Critic 标识本结果置信度较低（X.XX），建议人工复核」+ 链接接转人工审核（Concern #17）
- 🎯 用户教育：Onboarding Wizard 包含此说明（FR A9）

### 6. 学界合作合同模板（Provider Agreement）

- 📄 **`docs/legal/academic-provider-agreement.md`**
- 🎯 适用：吕老师及其他高校研究员上架算法时签
- 关键条款：
  - **分润比例**：100/0（自研）/ 60/40（合作课题组）/ 50/50（商业 Provider）
  - **IP 归属**：算法 IP 归原作者；OptiCloud 仅获得**调用 + 分发权**（非独占）
  - **学术伦理**：BibTeX 强制引用 + 教学模式开放
  - **合作期限**：1 年滚动 + 30 day notice 退出
  - **退出 SLA**：30 day 预通知 + 5y Image 归档 honor
  - **税务**：分润为 service fee，按个税 / 课题组事业单位入账
  - **跨校 / 多作者**：明示主负责人 + 分配比例 + 退休 / 转校 handover
- 🎯 适配：吕老师 M0 wk2 签发 Apache 2.0 时同步签合作合同

### 7. 数据出境同意书（DeepSeek/Qwen 境内已免；GPT/Claude 触发）

- 📄 **`docs/legal/data-export-consent-template.md`**
- 🎯 触发：用户在 Console 主动选 N4 远程国际 LLM（GPT-5.1 / Claude，v2+）时弹出
- 关键条款：
  - 数据出境**用户知情同意**
  - 出境后**境外接收方**（Anthropic / OpenAI）的合规承诺
  - **撤回权**（用户随时关闭，未来调用不再触发）
- 🎯 法规依据：《数据出境安全评估办法》+ PIPL §38-39

---

## 🟡 v2 启用前（M9+）

### 8. Webhook 服务协议（v2 启用）

- 📄 **`docs/legal/webhook-agreement.md`**
- 🎯 内容：HMAC-SHA256 签名机制 / 客户端验证义务 / 重试策略 / 失败补偿

### 9. Provider Public API 服务协议（v2 启用 P1-P8）

- 📄 **`docs/legal/provider-public-api-agreement.md`**

### 10. Marketplace 双边市场服务协议（v2 末 ¥40 万营收 hard-gate）

- 📄 **`docs/legal/marketplace-terms.md`**

---

## 🟡 v1.5 + 持续维护

### 11. 白帽 / Bug Bounty 协议（FR O4）

- 📄 **`docs/legal/security-bounty-terms.md`**
- 🎯 关键：CVSS 评分对应奖励（¥500-2,000）+ 反诈条款 + 公开致谢页

### 12. 教育版 / 学生使用协议

- 📄 **`docs/legal/student-edu-terms.md`**
- 🎯 关键：
  - 永久免费 2K/月 + Pro 30d trial
  - **禁止商用**（明示边界）
  - **.edu 邮箱有效性周期**（.edu 失效后转 personal plan 自动 prompt）
  - side project 检测 + 警告 SOP（多账户 / 高频 / 商业 API key）

### 13. 客户成功 SLA / 商业服务条款（v1.5+ Team/Enterprise）

- 📄 **`docs/legal/customer-success-sla.md`**
- 🎯 关键：响应时间 / 业务连续性承诺 / 升级路径

---

## 📅 实施 Timeline

| 阶段 | 必须完成 | Doc |
|---|---|---|
| **M0 wk1-2** | EPL/ECOS 法务签字（C21）| ADR-0003 |
| M0 wk1 | 法务律师 onboarding | — |
| **M1 末** | EULA + Privacy + DPA | Docs 2-4 |
| M2 | 法律咨询 hotline（24h，FR O10 配套） | — |
| **M5 前** | NL Summary 免责 + 学界合作合同 + 数据出境同意书 | Docs 5-7 |
| M7+ | Bug Bounty + Education Terms + Customer SLA | Docs 11-13 |
| v2 启用 | Webhook + Provider Public API + Marketplace | Docs 8-10 |

---

## 🤝 法务责任清单

| 角色 | 责任 |
|---|---|
| **课题组创始人** | 总览所有合同模板审定；C21 EPL/ECOS 签字 follow-up |
| **外聘法务律师** | 各模板起草 + 双语本地化 + 合规审查 |
| **运营 / Customer Success** | DPA 客户签约执行 + 法律问询响应（FR O10 24h SLA） |
| **工程 / DevOps** | 隐私政策技术兑现（TDE / 删除 SOP / 跨境标记）|
| **市场 / GTM** | EULA / Privacy 在 Landing / Console / Pricing 页面正确展示 |

---

## 🔗 关联文档

- 架构合规层：`_bmad-output/planning/architecture.md` § Step 4 D10 / C9 / C11
- PRD 合规规划：`_bmad-output/planning/prd.md` § Compliance & Regulatory
- ADR 索引：`docs/adr/`（含 ADR-0003 EPL/ECOS license decision）
- Runbooks：`docs/runbooks/`（应急响应含合规事件）
- Customer FAQs：`docs/customer-faqs/`（法务问答库 FR O10 配套）
