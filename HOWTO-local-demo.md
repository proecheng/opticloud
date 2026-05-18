# HOWTO — 30 分钟跑通本地 OptiCloud 演示

> 给非工程师 / 第一次跑代码的人。所有命令复制到 PowerShell（Windows）按 Enter。

## 前置（一次性安装，~15 分钟）

1. **Docker Desktop** — https://www.docker.com/products/docker-desktop/（下载并打开，等待右下角 Docker 图标变绿）
2. **uv**（Python 包管理器）— PowerShell 跑：
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
   关掉 PowerShell 再重开（让 PATH 生效）。
3. **Node.js 18+** — https://nodejs.org/（LTS 版本）
4. **pnpm**：
   ```powershell
   npm install -g pnpm
   ```

## 跑通本地 API 演示（10 分钟）

```powershell
cd D:\优化预测网站

# 1. 复制环境变量模板
Copy-Item .env.example .env

# 2. 启动 5 个本地服务（Postgres / Redis / Vault / MinIO / LocalStack）
docker-compose up -d

# 3. 检查 5 个容器都 healthy（等 30 秒）
docker-compose ps

# 4. 装 Python 依赖（首次 1-2 分钟）
uv sync

# 5. 启动 auth-service
cd apps\auth-service
uv run uvicorn auth_service.main:app --reload --port 8001
```

→ **浏览器打开** http://localhost:8001/docs — 你会看到自动生成的 OpenAPI 文档（Swagger UI），可以在浏览器里直接点 "Try it out" 测试 signup。

## 测试 signup endpoint（再开一个 PowerShell 窗口）

```powershell
# 注册新用户
curl.exe -X POST http://localhost:8001/v1/auth/signup `
  -H "Content-Type: application/json" `
  -d '{\"phone\":\"+8613800138000\",\"email\":\"test@example.com\"}'

# 期望输出：
# {
#   "user_id": "abc-123-...",
#   "jwt_access": "eyJhbGc...",
#   "jwt_refresh": "eyJhbGc...",
#   "edu_tier": false
# }
```

✅ **恭喜 — OptiCloud 第一个真实接口跑通了。**

## 测试创建 API Key

```powershell
# 用上一步的 jwt_access 替换 <JWT>
curl.exe -X POST http://localhost:8001/v1/auth/api_keys `
  -H "Authorization: Bearer <JWT>" `
  -H "Content-Type: application/json" `
  -d '{\"label\":\"my-first-key\",\"scope\":[\"optimize:write\"]}'

# 期望输出含 "api_key": "sk-XXXXX..." — 这是你的第一个 OptiCloud API Key
```

## 浏览 packages/ui 12 个组件（5 分钟）

```powershell
# 回到 repo 根
cd D:\优化预测网站

# 装 Node 依赖
pnpm install

# 启动 Storybook
cd packages\ui
pnpm storybook
```

→ **浏览器打开** http://localhost:6006 — 看 Tier 1 12 个组件在不同 variant 下的样子。

## J1 Vertical Slice 端到端 Demo（**最有视觉冲击力**）

前提：auth-service 已在 http://localhost:8001 运行（参考上面的 "跑通本地 API 演示" 节）。

```powershell
# 在另一个 PowerShell 窗口跑 web app
cd D:\优化预测网站\apps\web
pnpm install     # 首次需要（如果还没跑过 root 的 pnpm install）
pnpm dev
```

→ **浏览器打开** http://localhost:3000

**Demo 流程**：
1. **Landing**（http://localhost:3000）— 看到 OptiCloud 主页
2. 点击 **"立即注册"**
3. 填手机 `+8613800138000` + 邮箱 `test@example.com` → 点 **"立即注册 →"**
4. 自动跳转 **`/welcome`** — ConfirmationModal 弹出，含：
   - 完整 `sk-XXX...` API Key
   - **复制 cURL** 按钮
   - **📥 导入 Postman** 按钮（点击下载 `opticloud-postman-collection.json`）
5. 关掉 Modal — 看到 APIKeyManager 卡片 + masked 显示 + Reveal toggle

✅ **这是 J1 Vertical Slice 完整端到端 — Sprint 0 → Story 1.1a → 1.1b 全打通。**

## 停止本地服务

```powershell
cd D:\优化预测网站
docker-compose down
```

## 常见问题

**Q: docker-compose up 报 port 5432 已被占用？**
A: 你电脑上有别的 Postgres，改 `.env` 文件把 `5432:5432` 换成 `15432:5432`，或停掉本地 Postgres。

**Q: uv sync 报找不到 Python 3.12？**
A: 跑 `uv python install 3.12` 让 uv 自动装。

**Q: pnpm install 慢？**
A: 设置淘宝镜像：`pnpm config set registry https://registry.npmmirror.com/`
