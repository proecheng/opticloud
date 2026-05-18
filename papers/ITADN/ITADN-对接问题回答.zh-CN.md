# ITADN 对接问题回答

更新时间：2026-05-04

## 总体结论

当前已集成的 ITADN 程序更准确地说是一个 AIGC 文章处理底座，不是一个已经按 MicroGrid `POST /api/ai/forecast` 契约交付的预测 runtime。它目前主要由本地 Python 程序、ITADN 自有 MySQL 表、以及 OpenAI-compatible LLM 接口组成。

因此对接方式建议分两层：

1. 系统侧不要直接依赖 ITADN 内部脚本路径和数据库表结构，而是增加一个 adapter service。
2. adapter service 对上游保持稳定 HTTP 契约，对下游再调用 ITADN Python 模块、ITADN 数据库和 OpenAI-compatible 模型接口。

在 shadow/dry-run 阶段，必须继续保持不调用 VPP、不接生产 MQTT、不发真实控制，不写 MicroGrid 业务库。

## 如何跟 ITADN 接口

### 推荐接口方式

对外暴露一个系统自己的 HTTP adapter，例如：

| 场景 | 推荐路由 | 说明 |
| --- | --- | --- |
| ITADN 文本改写/导读 | `POST /api/itadn/rewrite` | 调用 ITADN 的 `rewrite_daodu`、`rewrite_middle`、`rewrite_conclusion` |
| ITADN 批处理触发 | `POST /api/itadn/jobs/rewrite` | 后台触发批量重写任务，不阻塞请求线程 |
| ITADN 健康检查 | `GET /health`、`GET /health/live`、`GET /health/ready` | adapter 自己提供 |
| MicroGrid AI forecast 兼容口 | `POST /api/ai/forecast` | 只有在 ITADN 后续确认提供 load/pv/price/tariff 预测模型后才接入真实预测 |

当前代码中可确认的 ITADN 能力是“论文/文章内容分割、改写、导读、总结”，不是电力负荷、光伏、电价、tariff 的 15 分钟预测。因此文档里的 `forecastTarget=load/pv/price/tariff` 需要标记为“待 ITADN 确认”，不能直接说已经支持。

### 下游调用方式

ITADN 内部调用模型时使用 OpenAI SDK 的 Chat Completions 兼容接口：

```python
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["ITADN_OPENAI_BASE_URL"],
    api_key=os.environ["ITADN_OPENAI_API_KEY"],
)

response = client.chat.completions.create(
    model=os.environ["ITADN_MODEL_NAME"],
    messages=[{"role": "user", "content": prompt}],
)
```

注意：代码中已有硬编码地址和数据库凭据，正式接入时必须迁移到 env-file 或 secret store，文档里只写 secret 来源，不写真实值。

## 如何调用 ITADN 里面的程序

### 方式一：命令行批处理

进入 ITADN-AIGC 目录后运行：

```powershell
python ITADN-AIGC-spilt.py
```

作用：从 ITADN 自有数据库读取原始文章，按摘要、正文、结论分割，写入 ITADN 自有中间表。

```powershell
python ITADN-AIGC-rewrite.py
```

作用：读取已分割内容，调用 LLM 改写摘要、正文、结论，并拼接成最终文章。

脚本里的关键参数：

| 参数 | 含义 |
| --- | --- |
| `START_ID` | 从哪个文章 ID 开始处理 |
| `BATCH_SIZE` | 每批处理多少篇 |
| `SECTION_MODE` | `abstract` / `middle` / `conclusion` / `all` |

### 方式二：Python 模块级调用

系统集成时更建议直接调用模块，而不是启动脚本进程：

```python
from rewrite_arxiv.process_module import ModuleProcessor

processor = ModuleProcessor()
processor.process_rewrite_tasks(
    start_id=1,
    batch_size=1,
    SECTION_MODE="all",
)
```

如果只调用模型改写能力：

```python
from rewrite_arxiv.arxiv_module_api import GPTUtil

gpt = GPTUtil()
daodu = gpt.rewrite_daodu(abstract_text)
middle = gpt.rewrite_middle(middle_text)
conclusion = gpt.rewrite_conclusion(conclusion_text)
```

### 方式三：HTTP adapter 封装

建议在你的系统中封装一个 HTTP 服务，内部调用 `GPTUtil` 或 `ModuleProcessor`：

```python
from fastapi import FastAPI
from pydantic import BaseModel
from rewrite_arxiv.arxiv_module_api import GPTUtil

app = FastAPI()
gpt = GPTUtil()

class RewriteRequest(BaseModel):
    section: str
    text: str

@app.post("/api/itadn/rewrite")
def rewrite(req: RewriteRequest):
    if req.section == "abstract":
        result = gpt.rewrite_daodu(req.text)
    elif req.section == "middle":
        result = gpt.rewrite_middle(req.text)
    elif req.section == "conclusion":
        result = gpt.rewrite_conclusion(req.text)
    else:
        raise ValueError("unsupported section")

    return {
        "result": result,
        "modelSource": "itadn-aigc-openai-compatible",
        "isFallback": False,
    }
```

长任务不要放在同步 HTTP 请求里跑，建议写入任务队列或后台 job，由前端/系统轮询 job 状态。

## Runtime owner 填写表建议答案

| 字段 | 建议填写值 |
| --- | --- |
| Runtime 类型 | AI inference / ITADN AIGC adapter |
| runtime owner/contact | ITADN 团队 + 本系统集成人员，具体负责人/群待确认 |
| 当前交付阶段 | shadow |
| 交付日期 | 2026-05-04 |
| 变更说明 | 接入 ITADN 现有 Python AIGC 处理链路；通过 adapter 对上提供稳定接口 |

| 字段 | 建议填写值 |
| --- | --- |
| registry path | 暂无正式 Docker image；待 ITADN 提供或由集成方封装 adapter 镜像 |
| image tag | 待镜像化后使用不可变 tag/digest，不能使用 `latest` |
| rollback image | 回退到原 `ai-inference-py` fixture/mock 或上一版 adapter 镜像 |
| 镜像架构 | 建议 linux/amd64；如需 arm64 待验证 |
| 是否需要私有 registry 登录 | 待镜像仓库确定；只写 secret source |

| 字段 | AI inference |
| --- | --- |
| `modelSource` | `itadn-aigc-openai-compatible:<model-alias>`，不要写真实 endpoint 或密钥 |
| fallback | 模型调用失败时返回原文或 baseline 结果，并标记 `isFallback=true`；MicroGrid shadow 继续保持 `commandIssued=false` |

| 字段 | 建议填写值 |
| --- | --- |
| `/health` | adapter 进程可响应即 200 |
| `/health/live` | Python/FastAPI 进程存活即 200 |
| `/health/ready` | env-file 存在、模型接口可访问、如启用批处理则 MySQL 连接池可用 |
| cold start | adapter 本身通常为秒级；真实耗时取决于远端模型接口和数据库连接 |
| timeout | 单次文本改写建议 60-180 秒；forecast shadow 建议 10-30 秒，超时走 fallback |

| 字段 | 建议填写值 |
| --- | --- |
| CPU | shadow 建议 2-4 vCPU |
| memory | shadow 建议 4-8 GB |
| GPU | 当前 adapter 侧不需要 GPU；如 ITADN 本地部署模型，GPU 由 ITADN 模型服务侧说明 |
| 磁盘/模型文件 | adapter 无本地大模型文件要求；日志和临时进度文件需可写目录 |
| 外部依赖 | ITADN MySQL、OpenAI-compatible LLM endpoint、可选 Wenyan/公众号发布工具 |

| 字段 | 建议填写值 |
| --- | --- |
| registry secret source | 待定，例如 `CI_REGISTRY_SECRET` |
| model secret source | `ITADN_OPENAI_API_KEY` / secret store 引用 |
| solver license source | 不需要 |
| safety strategy secret source | 不需要 |
| 本地 env-file 要求 | `deploy/docker/itadn-ai-shadow.env.local`，必须 ignored/local |

| 项 | 建议填写值 |
| --- | --- |
| HTTP route 是否保持不变 | 对 MicroGrid 兼容层保持 `POST /api/ai/forecast`；ITADN AIGC 能力另走 `/api/itadn/rewrite` |
| JSON 字段是否兼容 fixture | forecast fixture 待 ITADN 确认；AIGC rewrite 需新增独立 fixture |
| 是否写 MicroGrid 数据库 | 否；ITADN 只可写自己的业务库或经 adapter 返回结果 |
| 是否调用 VPP | 否 |
| 是否接生产 MQTT | 否 |
| 是否发真实控制 | 否 |

## ITADN 问题清单建议回答

| 问题 | 回答 |
| --- | --- |
| 谁是 AI runtime owner/contact | 待 ITADN 指定负责人；系统侧 owner 为集成人员 |
| 是否能交付 Docker image | 当前本机代码未发现 Docker image/Dockerfile；建议封装 FastAPI adapter 镜像 |
| Dapr/HTTP 契约能否保持 `POST /api/ai/forecast` | 可以由 adapter 保持；但 ITADN 当前代码不原生提供 forecast，需要 ITADN 确认预测能力 |
| `modelSource` 如何命名 | 建议 `itadn-aigc-openai-compatible:<model-alias>` |
| 支持哪些 `forecastTarget` | 当前代码未实现 load / pv / price / tariff；需 ITADN 另行确认 |
| 输入特征需要哪些 | 当前 AIGC 输入是文章 ID 或摘要/正文/结论文本；forecast 输入特征待确认 |
| 输出粒度和时间窗 | 当前 AIGC 输出是 Markdown 文本；未发现 15min 时间序列输出 |
| 是否需要 GPU | adapter 侧不需要；模型服务侧是否需要由 ITADN 确认 |
| cold start 和 timeout | adapter 秒级启动；单次 LLM 改写建议 60-180 秒超时 |
| fallback 策略 | LLM 调用失败返回原文或 baseline，并设置 `isFallback=true` |
| 模型仓库/secret 来源 | 使用 env-file/secret store，不写真实 token、endpoint、数据库密码 |
| 模型版本治理 | 使用 `ITADN_MODEL_NAME` 和 adapter 镜像 tag 记录版本；失败回退上一版 |
| 是否写数据库 | 不写 MicroGrid 数据库；当前 ITADN 会写自己的 MySQL 表 |
| 是否调用 VPP/MQTT/控制 | 否 |

## 需要立刻修正的集成风险

1. 代码里存在硬编码数据库连接信息和模型接口信息，必须迁移到环境变量或 secret store。
2. ITADN AIGC 程序会读写自己的数据库表，不应让它直接写 MicroGrid 的 Energy/Tariff/EMS 等业务库。
3. 批量重写是长任务，不适合作为同步接口直接调用，应通过 job/queue 运行。
4. 如果文档目标是 MicroGrid 预测 runtime，当前 ITADN AIGC 能力还不能直接回答 `forecastTarget`、15min 粒度、load/pv/price/tariff 等问题，需要 ITADN 提供预测模型或明确不支持。
