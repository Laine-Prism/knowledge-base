---
title: ContentHarvester — 微服务设计思考过程
date: 2026-06-11
source: 微信群文件分享
category: 技术/架构设计
summary_method: manual
---

## 📝 摘要

本文从架构师视角探讨了个人项目 ContentHarvester（内容采集系统）的微服务拆分策略。文章核心观点是：微服务拆分不应按功能模块机械切割，而要依据变更频率、资源特征、故障隔离、扩展需求和团队边界五个维度进行判断。

作者对比了三种拆分方案：A方案按技术能力拆分（6个服务），虽然技术栈纯粹但跨服务调用多；B方案按DDD业务领域拆分，内聚性好但单服务内资源需求冲突；C方案按运行特征拆分（4个服务），兼顾资源隔离与复杂度控制。最终推荐C方案——Web App、Crawler Worker、Media Worker、Scheduler四个服务，搭配Redis Streams作为消息队列。

关键决策依据包括：M2 MacBook 仅8GB内存的硬件限制、个人项目无需过度设计、爬虫（I/O密集）与ASR转录（CPU/内存密集）必须隔离。文章还设计了冷启动策略（Media Worker按需拉起，平时省3.5GB内存）和消息Topic体系，为实际落地提供了完整的技术路径。

---

## 📄 原文

# ContentHarvester — 微服务设计思考过程

> 架构师视角：不是"怎么拆"，而是"为什么这样拆"

---

## 一、微服务拆分的核心原则

拆微服务不是按"功能模块"乱切，而是根据以下 5 个维度判断：

| 维度 | 问题 | 如果答案是"是"→ 应该独立 |
|------|------|------------------------|
| **变更频率** | 这块功能是否经常独立变化？ | 爬虫接口经常变，转录引擎很少变 |
| **资源特征** | 是否有独特的资源需求？ | ASR 吃内存/CPU，爬虫吃网络和浏览器 |
| **故障隔离** | 它挂了是否应该影响其他部分？ | 爬虫被封不应该影响已有内容的查看 |
| **扩展需求** | 是否需要独立扩容？ | 批量采集时爬虫要扩，但前端不需要 |
| **团队边界** | 是否可以由不同的人独立开发？ | DeepSeek 写爬虫，同时另一个在写前端 |

---

## 二、三种拆法对比

### 方案 A：按技术能力拆（我之前给的）

```
Gateway → Web BFF → Crawler → Downloader → Transcriber → Scheduler
```
- 优点：每个服务技术栈纯粹
- 缺点：一个用户操作（如"采集抖音视频并转录"）要跨 4 个服务

### 方案 B：按业务领域拆（DDD 思路）

```
Gateway → Content Service → Media Service → Task Service
```
- Content Service = 文章采集 + 内容管理 + 导出
- Media Service = 视频下载 + 转录 + 音频处理
- Task Service = 定时调度 + 任务编排
- 优点：业务内聚，一个领域的事在一个服务里完成
- 缺点：Media Service 既有 I/O 密集（下载）又有计算密集（ASR）

### 方案 C：按运行特征拆（我推荐的 ⭐）

```
Gateway → Web App → Pipeline Workers → Scheduler
```

根据**运行时行为**来拆：

| 服务 | 运行特征 | 为什么独立 |
|------|---------|-----------|
| **Web App** | 低延迟、高并发、轻量 | 用户交互必须快，不能被后台任务拖慢 |
| **Crawler Worker** | I/O 密集、需要浏览器、不稳定 | 浏览器吃内存，可能被封，需要隔离 |
| **Media Worker** | CPU/内存密集、耗时长 | ASR 模型占 3GB，处理一个视频要几分钟 |
| **Scheduler** | 定时触发、编排协调 | 独立调度逻辑，不受工作节点影响 |

---

## 三、我的最终推荐：方案 C（按运行特征拆）

### 为什么？

1. **你的机器只有 8GB** — 服务越少，内存开销越小
2. **个人项目** — 不需要 6 个服务带来的运维复杂度
3. **核心矛盾是资源隔离** — 爬虫（浏览器）和 ASR（模型）互相抢资源，必须分开
4. **前端必须快** — 不能因为后台在转录就卡住页面

### 4 个服务 + 1 个消息队列

```
┌────────────────────────────────────────────────────────────────────┐
│                        Traefik / Nginx                              │
│                        (API Gateway + 前端托管)                      │
└───────────────────────────────┬────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ↓                   ↓                   ↓
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   Web App    │    │   Crawler    │    │    Media     │
    │              │    │   Worker     │    │   Worker     │
    │ ─ 内容管理   │    │              │    │              │
    │ ─ 搜索聚合   │    │ ─ 文章爬取   │    │ ─ 视频下载   │
    │ ─ 导出       │    │ ─ 平台搜索   │    │ ─ 音频提取   │
    │ ─ 通知       │    │ ─ 三级引擎   │    │ ─ ASR 转录   │
    │ ─ 前端 API   │    │ ─ Cookie 管理│    │ ─ 文件管理   │
    │              │    │              │    │              │
    │ FastAPI      │    │ FastAPI      │    │ FastAPI      │
    │ Vue 3 前端   │    │ Playwright   │    │ SenseVoice   │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │   Redis (消息队列     │
                    │   + 缓存 + 状态)     │
                    └──────────┬───────────┘
                               ↓
                    ┌──────────────────────┐
                    │   Scheduler Worker   │
                    │                      │
                    │ ─ 定时触发            │
                    │ ─ 任务编排            │
                    │ ─ 重试/去重           │
                    └──────────────────────┘
                               ↓
                    ┌──────────────────────┐
                    │   PostgreSQL         │
                    │   (所有持久化数据)    │
                    └──────────────────────┘
```

---

## 四、4 个服务详细设计

### 服务 1: Web App — "门面"

```
角色：用户直接交互的唯一入口
特征：低延迟、无状态、轻量
端口：8000
内存：~300MB
```

| 职责 | 说明 |
|------|------|
| 前端托管 | Vue 3 SPA |
| 内容 CRUD | 列表/详情/编辑/收藏/标签/搜索 |
| 聚合查询 | 从 DB 读内容，不直接调爬虫 |
| 导出 | Word / PDF / Markdown 生成 |
| 通知 | WebSocket 推送 + 通知列表 |
| 任务下发 | 用户点"采集" → 发消息到队列 |

**不做**：不爬取、不下载、不转录。只负责"收请求、发任务、展示结果"。

```python
# Web App 收到采集请求后的逻辑
async def request_crawl(url: str):
    task_id = generate_id()
    # 不自己爬！发消息到队列让 Worker 去做
    await message_queue.publish("crawl.requested", {
        "task_id": task_id,
        "url": url,
        "platform": detect_platform(url)
    })
    return {"task_id": task_id, "status": "queued"}
```

---

### 服务 2: Crawler Worker — "爬虫工人"

```
角色：消费队列消息，执行爬取任务
特征：I/O 密集、需要浏览器实例、可能被反爬
端口：8001
内存：~1GB（浏览器实例吃内存）
```

| 职责 | 说明 |
|------|------|
| 消费消息 | 监听 `crawl.requested` 队列 |
| 文章爬取 | 公众号、头条全文 |
| 平台搜索 | 关键词 → 各平台搜索结果 |
| 三级引擎 | DrissionPage → Playwright → browser-use |
| Cookie 池 | 登录态管理 |
| 结果回写 | 爬取完成 → 写入 DB + 发 `crawl.completed` 消息 |

```python
# Crawler Worker 的工作循环
async def consume_crawl_tasks():
    async for message in queue.subscribe("crawl.requested"):
        try:
            content = await smart_browser.fetch(message.url, message.platform)
            await database.save_content(content)
            await queue.publish("crawl.completed", {
                "task_id": message.task_id,
                "content_id": content.id
            })
        except AllEnginesFailedError as e:
            await queue.publish("crawl.failed", {
                "task_id": message.task_id,
                "reason": str(e)
            })
```

---

### 服务 3: Media Worker — "多媒体工人"

```
角色：视频下载 + 音频提取 + 语音转录
特征：CPU/内存密集、处理时间长
端口：8002
内存：~3.5GB（SenseVoice 模型 + 处理缓冲）
```

| 职责 | 说明 |
|------|------|
| 消费消息 | 监听 `download.requested` 和 `transcribe.requested` |
| 视频解析 | 抖音、视频号真实地址解析 |
| 视频下载 | 无水印高清下载 |
| 音频提取 | FFmpeg 从视频提取音频 |
| ASR 转录 | SenseVoice 逐字转录 |
| 文件清理 | 转录完成后可选删除视频 |

**为什么把下载和转录放一起？**
- 它们是一个**流水线**：下载 → 提取音频 → 转录
- 放一起避免大文件在服务间传输
- 共享文件存储目录

```python
# Media Worker 的处理流水线
async def process_video(message):
    # 1. 下载视频
    video_path = await downloader.download(message.url, message.platform)
    
    # 2. 提取音频
    audio_path = await audio_extractor.extract(video_path)
    
    # 3. ASR 转录
    transcript = await transcriber.transcribe(audio_path)
    
    # 4. 保存结果
    await database.save_transcript(message.content_id, transcript)
    
    # 5. 清理视频文件（可选保留）
    if config.auto_cleanup:
        await file_storage.delete(video_path)
    
    # 6. 通知完成
    await queue.publish("transcription.completed", {
        "task_id": message.task_id,
        "content_id": message.content_id
    })
```

---

### 服务 4: Scheduler — "调度员"

```
角色：定时触发 + 任务编排 + 状态追踪
特征：轻量、定时触发、协调多个 Worker
端口：8003
内存：~200MB
```

| 职责 | 说明 |
|------|------|
| 定时触发 | Cron 表达式，定时发任务到队列 |
| 任务编排 | 一个"采集视频"任务 = 爬取 → 下载 → 转录 的编排 |
| 状态机 | 跟踪每个任务：queued → running → completed/failed |
| 去重 | 相同 URL 24 小时内不重复 |
| 重试 | 失败任务自动重试（最多 3 次） |
| 批量管理 | 关键词搜索后批量下发子任务 |

```python
# 任务编排：一个完整的"视频采集"流程
class VideoPipeline:
    """编排：搜索 → 下载 → 转录"""
    
    states = ["searching", "downloading", "transcribing", "completed", "failed"]
    
    async def start(self, keyword: str, platform: str):
        # Step 1: 搜索热门视频
        await queue.publish("crawl.search", {
            "keyword": keyword,
            "platform": platform,
            "pipeline_id": self.id
        })
        self.state = "searching"
    
    async def on_search_completed(self, results):
        # Step 2: 对每个视频发下载任务
        for video in results[:10]:  # 取前 10 个
            await queue.publish("download.requested", {
                "url": video.url,
                "pipeline_id": self.id
            })
        self.state = "downloading"
    
    async def on_download_completed(self, file_info):
        # Step 3: 下载完成，发转录任务
        await queue.publish("transcribe.requested", {
            "audio_path": file_info.audio_path,
            "pipeline_id": self.id
        })
        self.state = "transcribing"
```

---

## 五、消息队列设计

### 为什么选 Redis Streams（而不是 RabbitMQ/Kafka）？

| 对比 | Redis Streams | RabbitMQ | Kafka |
|------|-------------|----------|-------|
| 额外部署 | 不需要（已有 Redis） | 需要单独部署 | 需要 + ZooKeeper |
| 内存占用 | 共享 Redis 的 128MB | 额外 300MB+ | 额外 1GB+ |
| 复杂度 | 简单 | 中等 | 高 |
| 消息可靠性 | 够用（ACK + 重试） | 强 | 最强 |
| 适合你的场景 | ✅ | 过重 | 过重 |

**结论**：个人项目 + 8GB 内存，Redis Streams 是最优解。轻量、够用、零额外部署。

### 队列 Topic 设计

```
crawl.requested          # Web App → Crawler Worker
crawl.search.requested   # Scheduler → Crawler Worker  
crawl.completed          # Crawler Worker → Web App / Scheduler
crawl.failed             # Crawler Worker → Scheduler (重试)

download.requested       # Scheduler / Web App → Media Worker
download.completed       # Media Worker → Scheduler

transcribe.requested     # Media Worker 内部 / Scheduler → Media Worker
transcription.completed  # Media Worker → Web App (通知用户)

notification.send        # 任何服务 → Web App (推送通知)
```

---

## 六、M2 8GB 内存优化策略

```
┌─ 全量运行（开发调试全部功能时）─────────────────┐
│                                                │
│  PostgreSQL:     512MB                         │
│  Redis:          128MB                         │
│  Web App:        300MB                         │
│  Crawler Worker: 1GB (浏览器)                   │
│  Media Worker:   3.5GB (ASR 模型)              │
│  Scheduler:      200MB                         │
│  ──────────────────────────                    │
│  总计:           ~5.6GB + 系统 → 刚好够         │
│                                                │
└────────────────────────────────────────────────┘

┌─ 日常运行（不需要转录时）──────────────────────┐
│                                                │
│  PostgreSQL + Redis + Web App + Scheduler      │
│  = ~1.2GB                                      │
│  Crawler Worker 按需启动                        │
│  Media Worker 按需启动（有转录任务时才拉起）      │
│                                                │
└────────────────────────────────────────────────┘
```

**关键优化**：Media Worker 采用**冷启动模式**
- 平时不运行（省 3.5GB）
- 有转录任务时 Scheduler 自动拉起
- 转录完成后可选自动关闭

---

## 七、开发时的启动方式

```bash
# 启动基础设施 + Web（日常浏览/管理内容）
docker compose up postgres redis web-bff frontend

# 需要爬取时，额外启动
docker compose up crawler

# 需要转录时，额外启动
docker compose up media-worker

# 全部启动
docker compose up
```

---

## 八、容错设计

| 场景 | 处理方式 |
|------|---------|
| Crawler 被封了 | 消息留在队列，等恢复后继续消费；或引擎降级到 browser-use |
| Media Worker 内存不够崩溃 | Docker 自动重启 + 未完成任务留在队列自动重试 |
| DB 挂了 | Web App 返回"服务暂时不可用"，Worker 暂停消费 |
| 网络断了 | 消息持久化在 Redis，网络恢复后继续 |
| 用户同时提交 100 个任务 | 队列削峰，Worker 按能力一个个处理 |

---

## 九、服务间不共享数据库（但共享一个 PostgreSQL 实例）

```sql
-- 用 Schema 隔离，逻辑上独立
CREATE SCHEMA web_app;       -- Web App 的表
CREATE SCHEMA crawler;       -- Crawler 的表（Cookie 等）
CREATE SCHEMA media;         -- Media 的表（文件记录）
CREATE SCHEMA scheduler;     -- Scheduler 的表（任务定义）

-- 核心内容表放在 public schema，多服务共享读
-- 只有负责写入的服务才写，其他服务只读
```

| 表 | 谁写 | 谁读 |
|----|------|------|
| contents | Crawler Worker, Media Worker | Web App, Scheduler |
| scheduled_tasks | Scheduler | Web App |
| notifications | 所有服务 | Web App |
| cookies | Crawler Worker | Crawler Worker |
| file_records | Media Worker | Web App |

---

## 十、总结对比

| 维度 | 方案 A (6 服务) | 方案 C (4 服务，推荐) |
|------|---------------|---------------------|
| 服务数量 | 6 | 4 |
| 内存占用 | ~7GB（紧张） | ~5.6GB（刚好） |
| 运维复杂度 | 高 | 中 |
| 开发效率 | 低（服务多跳来跳去） | 高（关注点集中） |
| 故障隔离 | 强 | 足够强 |
| 适合 8GB M2 | ⚠️ | ✅ |

---

## 十一、最终确认

**4 个微服务：**

| # | 服务 | 核心定位 | 资源特征 |
|---|------|---------|---------|
| 1 | **Web App** | 用户界面 + 内容管理 | 轻量、常驻 |
| 2 | **Crawler Worker** | 爬虫 + 搜索 | I/O 密集、按需 |
| 3 | **Media Worker** | 下载 + 转录 | CPU/内存密集、按需 |
| 4 | **Scheduler** | 定时 + 编排 | 轻量、常驻 |

**+基础设施：** PostgreSQL + Redis（消息队列 + 缓存）

**你同意这个拆法吗？**

