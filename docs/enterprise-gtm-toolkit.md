# Enterprise GTM Toolkit

> **Owner**：销售 / Customer Success 团队（v1.5 起启动）+ 创始人（v1 期间个案处理）
> **Status**：🚧 骨架 / Skeleton（M3-M5 商用前 ready）
> **关联架构**：`_bmad-output/planning/architecture.md` Appendix E / Gap G19
> **Last Updated**：2026-05-17

---

## 📋 用途

OptiCloud 主要面向**中型企业的优化 / 数据科学 / 算法工程师**（PRD §1109 主 persona）。本文档覆盖：

- 大客户企业采购流程兼容性
- 企业 IT 部门信任建立
- 从 Gurobi / DataRobot 等的迁移工具
- 集成现有系统的 connector library
- 企业级 SLA 个案签约能力

---

## 🚨 M5 商用前必须 ready（Gap G19）

### 1. 企业采购流程模板

#### 1.1 PO（Purchase Order）模板

- 📄 **`docs/gtm/po-template.md`**
- 🎯 内容：
  - 项目编号 / 部门 / 采购理由
  - OptiCloud Plan 选项（Team / Enterprise 报价）
  - 计费周期（月付 / 季付 / 年付）+ 折扣
  - **统一发票**（增值税专用发票 / 普通发票）
  - 合同期限 + 自动续约条款
  - 终止 / 退款条款（联动 EULA）

#### 1.2 SOW（Statement of Work）模板

- 📄 **`docs/gtm/sow-template.md`**
- 🎯 内容：项目范围 / 交付物 / 验收标准 / 客户成功支持级别

#### 1.3 招标响应模板

- 📄 **`docs/gtm/rfi-rfp-template.md`**
- 🎯 内容：标准 RFI / RFP 响应模板（含技术规格 / 合规证书 / 案例）

#### 1.4 框架协议（Master Service Agreement / MSA）

- 📄 **`docs/gtm/msa-template.md`**
- 🎯 适用：年合作 ≥¥10 万的客户

#### 1.5 增值税发票流程

- 📄 **`docs/gtm/invoice-process.md`**
- 🎯 内容：开票流程（自助 + 人工 + 红字发票）+ 财务对账

---

### 2. SOC 2 / ISO 27001 启动（v1.5 起 ramp up）

#### 2.1 SOC 2 Type II 路线图

- 📄 **`docs/gtm/soc2-roadmap.md`**
- 🎯 时间窗：
  - **v1.5（M9+）启动评估**（需要 6-12 月 observation period）
  - **v2 末（M13+）取证**（与等保 2.0 三级并行）
- 🎯 范围：Security / Availability / Confidentiality（先 3 类，Processing Integrity + Privacy 后续）
- 🎯 关键控制：与 P40 Service Auth / P59 Resilience / P34 AIGC Filter / Audit Log 等 mapping

#### 2.2 ISO 27001 / ISO 27018 启动

- 📄 **`docs/gtm/iso-27001-roadmap.md`**
- 🎯 ISO 27001 信息安全管理体系（与等保 2.0 二级互补）
- 🎯 ISO 27018 云隐私（与 PIPL 互补）

#### 2.3 SOC 2 / ISO 27001 报告共享流程

- 📄 **`docs/gtm/audit-report-sharing.md`**
- 🎯 内容：客户提需求 → NDA → 报告共享 portal

---

### 3. 迁移工具（Gurobi / DataRobot / 其他）

#### 3.1 Gurobi 迁移 Wizard

- 📄 **`docs/gtm/gurobi-migration-guide.md`**
- 🎯 工具：
  - **代码翻译器**：Gurobi Python API → OptiCloud API（automated codemod 工具 v1.5 起）
  - **结果对比**：用户上传 Gurobi 历史结果 → OptiCloud 重跑 → diff 报告
  - **双跑期**：3 个月 dual-run 免费（建立信任）
  - **License 处置**：Gurobi 剩余 license 周期 OptiCloud 配套折扣
- 🎯 营销页：`https://opticloud.cn/migrate/from-gurobi`

#### 3.2 DataRobot / RapidMiner 迁移

- 📄 **`docs/gtm/datarobot-migration-guide.md`**

#### 3.3 PyPSA / 自建求解器迁移

- 📄 **`docs/gtm/pypsa-migration-guide.md`**

---

### 4. Industry Connector POC（v2 启动 3-5 个）

#### 4.1 SAP 集成

- 📄 **`docs/gtm/connectors/sap-connector.md`**
- 🎯 形式：Python SDK + Pre-built BAPI / OData mapping
- 🎯 用例：SAP 物流模块（VRPTW）/ 生产计划（MILP）/ 库存优化（预测）

#### 4.2 Oracle ERP 集成

- 📄 **`docs/gtm/connectors/oracle-connector.md`**

#### 4.3 Salesforce 集成

- 📄 **`docs/gtm/connectors/salesforce-connector.md`**
- 🎯 用例：Sales forecasting / Lead scoring / 路径优化

#### 4.4 TMS（运输管理系统）集成

- 📄 **`docs/gtm/connectors/tms-connector.md`**
- 🎯 目标 TMS：钉钉云物流 / 大数据物流 / 顺丰科技

#### 4.5 WMS（仓储管理系统）集成

- 📄 **`docs/gtm/connectors/wms-connector.md`**

---

### 5. 企业级 SLA 个案签约能力（v1.5 起）

#### 5.1 Enterprise SLA 模板

- 📄 **`docs/gtm/enterprise-sla-template.md`**
- 🎯 内容：
  - 可用性 99.5% / 99.9% / 99.95% 三档（vs 标准 Pro 99.5%）
  - 响应时间 SLA：P0 15min / P1 4h / P2 next business day
  - 故障赔偿：根据 SLA tier 退款 + 服务延期
  - 法务问询 24h SLA（FR O10 增强）

#### 5.2 Enterprise SLA 报价表

- 📄 **`docs/gtm/enterprise-sla-pricing.md`**

---

## 🟠 Important（M5-M7 ramp up）

### 6. Customer Success 流程

#### 6.1 Onboarding Playbook

- 📄 **`docs/gtm/customer-success-onboarding.md`**
- 🎯 阶段：
  - **Day 0**：合同签约 + 引导邮件
  - **Week 1**：技术 onboarding 会议（1h）+ 个性化 API key 创建
  - **Month 1**：First Use Case 验证（CSM 主动 follow up）
  - **Quarter 1**：QBR（Quarterly Business Review）+ ROI 展示

#### 6.2 Account Management 工具

- 📄 **`docs/gtm/account-management.md`**
- 🎯 CRM 选型：HubSpot Free Tier（v1.5）→ Salesforce（v2+）

#### 6.3 NPS / CSAT 调查流程

- 📄 **`docs/gtm/nps-csat-process.md`**
- 🎯 频率：季度 NPS + 关键 milestone CSAT

---

### 7. Algorithm Selection Wizard（架构 P68 联动）

- 📄 **`docs/gtm/algorithm-wizard-design.md`**
- 🎯 形态：Console 内 wizard，引导用户选择 SKU
  - 输入问题（自然语言 OR 结构化）
  - 推荐 ≥ 2 个 SKU（含理由 + 预估 Credits + 预估解时长）
  - 一键试用模板（含 sample data）
- 🎯 技术实现：基于 capability-registry + prompt-store（P68）+ Critic Agent

---

### 8. 跨语言支持（v1.5 全栈 en-US）

- 📄 **`docs/gtm/i18n-rollout.md`**
- 🎯 时间窗：v1.5（M6+ PRD §1727）启动全栈 en-US 翻译
- 🎯 优先级：Landing → Pricing → Docs → Console → Error messages
- 🎯 v2-v3：日 / 韩 / 西 / 阿（按海外 BD 启动）

---

### 9. 公开案例（Customer Story）

- 📄 **`docs/gtm/customer-stories-template.md`**
- 🎯 内容：
  - 客户 challenge / OptiCloud 解决方案 / 量化结果 / quote
  - **Lighthouse customer**：J1 物流主管李工 / J5 陈架构师 等 PRD 主 persona 实际原型客户

---

### 10. Pricing Page Optimization

- 📄 **`docs/gtm/pricing-page-optimization.md`**
- 🎯 A/B test framework + 热力图 + 转化分析

---

## 🟡 Nice-to-Have（v2+）

### 11. Partner / Reseller Program

- 📄 **`docs/gtm/partner-reseller-program.md`**

### 12. Account-Based Marketing（ABM）

- 📄 **`docs/gtm/abm-playbook.md`**

### 13. Conference / Event Strategy

- 📄 **`docs/gtm/conference-strategy.md`**
- 🎯 重点会议：INFORMS / IEEE / 中国运筹学会 / 数据智能大会

---

## 📅 实施 Timeline

| 阶段 | 必须完成 | Doc |
|---|---|---|
| **M3 末**（GTM 准备）| PO / SOW 模板 + Pricing Page | Doc 1.1, 1.2, 10 |
| **M4.5**（PRD GTM 锚点）| MSA + Customer Story 2-3 + 营销素材 | Doc 1.4, 9 |
| **M5 商用前** | 增值税发票 + Enterprise SLA + 至少 1 个 Gurobi 迁移工具原型 | Doc 1.5, 5, 3.1 |
| **v1.5（M7+）** | SOC 2 Type II 启动 / Customer Success 流程 / i18n | Doc 2.1, 6, 8 |
| **v2 末** | SOC 2 取证 / 3-5 个 connector POC / Algorithm Wizard | Doc 2, 4, 7 |
| **v3+** | Partner Program / ABM | Doc 11, 12 |

---

## 🤝 责任清单

| 角色 | 责任 |
|---|---|
| **销售总监 / Customer Success Lead** | 各模板维护 + 大客户对接 |
| **法务律师** | PO/SOW/MSA/Enterprise SLA 起草 + 审定 |
| **创始人** | v1 期间个案处理（无销售团队）|
| **市场 / 营销** | Customer Story 撰写 + Pricing 优化 |
| **DevOps** | SOC 2 / ISO 27001 技术控制 mapping |
| **工程团队** | Industry Connector / Algorithm Wizard 开发 |

---

## 🔗 关联文档

- 架构 GTM 锚点：`_bmad-output/planning/architecture.md` § PRD §1296 (M4.5 GTM 准备)
- 法律模板：`docs/legal-templates.md`
- Runbooks：`docs/runbooks/`
- Customer FAQs：`docs/customer-faqs/`
