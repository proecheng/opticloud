# @opticloud/web

OptiCloud Web Console — **Next.js 15 App Router**.

**Currently implemented**: Story 1.1a + 1.1b — J1 Vertical Slice (Landing → Signup → Welcome with API Key Modal + Postman 一键导入).

## Routes

| Route | Story | Description |
|---|---|---|
| `/` | — | Landing page (UX Direction: Engineer-First / 实证克制) |
| `/auth/signup` | **1.1a** | 手机+邮箱注册表单 |
| `/welcome` | **1.1b** | 注册成功 + 自动创建 API Key + ConfirmationModal + Postman 导入 |
| `/404` | — | EmptyState fallback (Recovery-Forward direction) |

## Prereqs

1. **auth-service running** at `http://localhost:8001` (Story 0.6) — start with:
   ```bash
   cd ../auth-service && uv run uvicorn auth_service.main:app --reload --port 8001
   ```
2. **packages/ui** built (workspace dep auto-resolved by pnpm).

## Quickstart

```bash
# From repo root:
pnpm install

# Run dev server
cd apps/web
pnpm dev
# → http://localhost:3000
```

## Demo flow (J1 happy path)

1. Open http://localhost:3000 — Landing page
2. Click "立即注册"
3. Fill `+8613800138000` + `you@example.com` → "立即注册 →"
4. Auto-redirect to `/welcome`
5. ConfirmationModal pops up with full `sk-XXX_...` API Key + cURL example
6. Click "复制 cURL" → check clipboard
7. Click "📥 导入 Postman" → download `opticloud-postman-collection.json`
8. Verify API Key card shows masked key + Reveal toggle (CRG12)

## Architecture references

- **Story 1.1a** Web UI 注册 + API Key（FR A1 + A2）
- **Story 1.1b** ConfirmationModal + cURL + Postman 一键导入（FG1.1 Critical）
- **CRG12** API Key mask + Reveal toggle + Modal warning
- **FG1.1** Postman Workspace M1 Critical
- **P75** Persona-Surface Mapping — 李工 cURL surface
- **P76** Page Direction Map — Landing / Auth / Welcome
- **packages/ui Tier 1** APIKeyManager / ConfirmationModal / StatusCard / RFC7807Panel / EmptyState
