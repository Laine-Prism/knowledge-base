---
title: ContentHarvester — 技术详细设计文档（TDD）
date: 2026-06-11
source: 微信群文件分享
category: 技术/架构设计
summary_method: manual
---

## 📝 摘要

这是 ContentHarvester 项目的完整技术详细设计文档（TDD），涵盖18个设计维度，为系统开发提供了从架构到实现的全方位蓝图。系统采用4微服务架构（Web App + Crawler Worker + Media Worker + Scheduler），以Nginx做网关，Redis Streams做消息队列，PostgreSQL做持久化。

核心技术亮点包括：三级浏览器引擎降级策略（DrissionPage→Playwright→browser-use，按反爬强度逐级升级）；视频下载与转录流水线（yt-dlp下载 + ffmpeg提取音频 + SenseVoice中文ASR）；热度排序算法（综合点赞/评论/转发加权 + 时间衰减因子）；以及完整的导出系统（Markdown/PDF/Notion/飞书多格式）。

文档还详细设计了数据模型（Contents、Tasks、Notifications三大核心表）、RESTful API接口规范、定时调度策略（支持Cron表达式）、通知系统（WebSocket实时推送）、前端架构（Vue3 + Naive UI + Pinia状态管理）、测试金字塔策略以及安全防护措施。全部技术决策记录在ADR附录中，包括选择Redis Streams而非RabbitMQ、SenseVoice而非Whisper等关键抉择的理由。

---

## 📄 原文

# ContentHarvester — 技术详细设计文档（TDD）

> 版本：v1.0  
> 状态：✅ 架构已确认，可进入开发  
> 日期：2026-06-10

---

## 目录

1. [系统总览](#一系统总览)
2. [服务详细设计](#二服务详细设计)
3. [数据模型设计](#三数据模型设计)
4. [API 接口设计](#四api-接口设计)
5. [消息队列设计](#五消息队列设计)
6. [三级浏览器引擎设计](#六三级浏览器引擎设计)
7. [各平台爬虫设计](#七各平台爬虫设计)
8. [视频下载与转录流水线](#八视频下载与转录流水线)
9. [热度排序算法设计](#九热度排序算法设计)
10. [导出模块设计](#十导出模块设计)
11. [定时调度设计](#十一定时调度设计)
12. [通知系统设计](#十二通知系统设计)
13. [配置管理设计](#十三配置管理设计)
14. [错误处理与容错设计](#十四错误处理与容错设计)
15. [部署设计](#十五部署设计)
16. [前端设计](#十六前端设计)
17. [测试策略](#十七测试策略)
18. [安全设计](#十八安全设计)

---

## 一、系统总览

### 1.1 架构全景图

```
                        ┌───────────────────────┐
                        │      用户浏览器        │
                        └───────────┬───────────┘
                                    │ HTTP/WebSocket
                        ┌───────────▼───────────┐
                        │    Nginx Gateway      │
                        │    (反向代理+静态资源)  │
                        └───────────┬───────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
        /api/*   │        /ws      │       /*         │
                 ▼                  ▼                  ▼
        ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
        │   Web App    │  │  WebSocket   │  │   Frontend   │
        │   (FastAPI)  │  │   Handler    │  │   (Vue SPA)  │
        │   Port:8000  │  │              │  │   静态文件    │
        └──────┬───────┘  └──────────────┘  └──────────────┘
               │
               │  Publish / Subscribe
               ▼
        ┌──────────────────────────────────────────────────┐
        │              Redis                                │
        │  ┌─────────────┐  ┌──────────┐  ┌────────────┐  │
        │  │   Streams   │  │  Cache   │  │  Pub/Sub   │  │
        │  │  (消息队列)  │  │ (缓存)   │  │ (实时通知) │  │
        │  └─────────────┘  └──────────┘  └────────────┘  │
        └────────┬──────────────┬──────────────┬───────────┘
                 │              │              │
        ┌────────▼───────┐ ┌───▼────────┐ ┌──▼───────────┐
        │ Crawler Worker │ │Media Worker│ │  Scheduler   │
        │   Port:8001    │ │  Port:8002 │ │  Port:8003   │
        └────────┬───────┘ └───┬────────┘ └──┬───────────┘
                 │              │              │
                 └──────────────┼──────────────┘
                                ▼
                 ┌──────────────────────────────┐
                 │        PostgreSQL             │
                 │   ┌────────┐ ┌────────────┐  │
                 │   │ public │ │  schemas   │  │
                 │   │(共享表)│ │(各服务私有) │  │
                 │   └────────┘ └────────────┘  │
                 └──────────────────────────────┘
                                │
                 ┌──────────────▼──────────────┐
                 │       File Storage           │
                 │   (本地磁盘 /data/files)     │
                 └─────────────────────────────┘
```

### 1.2 技术栈确认

| 层级 | 技术 | 版本 |
|------|------|------|
| 语言 | Python | 3.11+ |
| Web 框架 | FastAPI | 0.110+ |
| 前端 | Vue 3 + TypeScript + Vite | Vue 3.4+ |
| UI 库 | Naive UI | 2.38+ |
| 数据库 | PostgreSQL | 16 |
| 缓存/队列 | Redis (Streams) | 7 |
| ORM | SQLAlchemy 2.0 (async) | 2.0+ |
| 迁移 | Alembic | 1.13+ |
| 浏览器自动化 L1 | DrissionPage | 4.0+ |
| 浏览器自动化 L2 | Playwright | 1.42+ |
| 浏览器自动化 L3 | browser-use + DeepSeek | 最新 |
| 视频下载 | yt-dlp + 定制解析器 | 最新 |
| ASR | SenseVoice (FunASR) | 最新 |
| 音频处理 | FFmpeg | 6+ |
| 文档导出 | python-docx / WeasyPrint | 最新 |
| 容器化 | Docker + Docker Compose | 最新 |
| 网关 | Nginx | 1.25+ |

---

## 二、服务详细设计

### 2.1 Web App Service

```
services/web-app/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── contents.py        # GET/PUT/DELETE 内容
│   │   │   ├── crawl.py           # POST 提交采集任务
│   │   │   ├── export.py          # POST 导出
│   │   │   ├── notifications.py   # GET 通知列表
│   │   │   ├── search.py          # POST 搜索
│   │   │   └── tasks.py           # CRUD 定时任务
│   │   ├── schemas/
│   │   │   ├── content.py         # Content 请求/响应模型
│   │   │   ├── crawl.py           # 采集请求模型
│   │   │   ├── export.py          # 导出请求模型
│   │   │   ├── notification.py    # 通知模型
│   │   │   ├── search.py          # 搜索请求/响应模型
│   │   │   └── task.py            # 定时任务模型
│   │   ├── deps.py                # 依赖注入
│   │   └── middleware.py          # 中间件（日志、异常处理）
│   ├── application/
│   │   ├── manage_content.py      # 内容增删改查用例
│   │   ├── export_content.py      # 导出用例
│   │   ├── request_crawl.py       # 发起采集请求用例
│   │   ├── request_search.py      # 发起搜索用例
│   │   └── manage_notification.py # 通知管理用例
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── content.py         # Content 实体
│   │   │   ├── notification.py    # Notification 实体
│   │   │   └── export_request.py  # 导出请求实体
│   │   ├── ports/
│   │   │   ├── content_repository.py
│   │   │   ├── notification_repository.py
│   │   │   ├── message_publisher.py
│   │   │   ├── exporter.py
│   │   │   └── realtime_notifier.py
│   │   ├── value_objects/
│   │   │   ├── platform.py        # Platform 枚举
│   │   │   ├── content_status.py  # 状态枚举
│   │   │   └── export_format.py   # 导出格式枚举
│   │   └── exceptions.py
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── database.py        # 异步连接池
│   │   │   ├── models.py          # ORM 模型
│   │   │   ├── content_repo.py    # ContentRepository 实现
│   │   │   └── notification_repo.py
│   │   ├── messaging/
│   │   │   └── redis_publisher.py # Redis Streams 发布者
│   │   ├── exporters/
│   │   │   ├── markdown_exporter.py
│   │   │   ├── word_exporter.py
│   │   │   └── pdf_exporter.py
│   │   ├── realtime/
│   │   │   └── websocket_notifier.py
│   │   └── container.py           # 依赖注入容器
│   ├── main.py
│   └── config.py
├── tests/
├── Dockerfile
└── requirements.txt
```

**核心职责边界：**
- ✅ 接收用户请求、返回数据
- ✅ 内容的 CRUD 操作（读写数据库）
- ✅ 导出文件（Word/PDF/Markdown）
- ✅ WebSocket 实时推送通知
- ✅ 发消息到队列（触发采集/搜索/转录）
- ❌ 不爬取、不下载、不转录

---

### 2.2 Crawler Worker Service

```
services/crawler/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── health.py          # 健康检查
│   │   └── schemas/
│   ├── application/
│   │   ├── crawl_article.py       # 爬取文章用例
│   │   ├── search_content.py      # 搜索用例
│   │   └── manage_login.py        # 登录管理用例
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── crawl_result.py    # 爬取结果实体
│   │   │   └── search_result.py   # 搜索结果实体
│   │   ├── ports/
│   │   │   ├── browser_engine.py  # 浏览器引擎接口
│   │   │   ├── article_crawler.py # 文章爬虫接口
│   │   │   ├── content_searcher.py# 搜索接口
│   │   │   ├── cookie_store.py    # Cookie 存储接口
│   │   │   └── message_consumer.py# 消息消费接口
│   │   ├── services/
│   │   │   ├── engine_fallback.py # 引擎降级策略
│   │   │   └── scoring.py         # 热度排序算法
│   │   └── exceptions.py
│   ├── infrastructure/
│   │   ├── browser/
│   │   │   ├── drission_engine.py     # L1: DrissionPage
│   │   │   ├── playwright_engine.py   # L2: Playwright
│   │   │   ├── browseruse_engine.py   # L3: browser-use
│   │   │   └── smart_browser.py       # 智能降级适配器
│   │   ├── crawlers/
│   │   │   ├── wechat_article.py      # 微信公众号爬虫
│   │   │   └── toutiao_article.py     # 今日头条爬虫
│   │   ├── searchers/
│   │   │   ├── wechat_searcher.py     # 公众号搜索
│   │   │   ├── toutiao_searcher.py    # 头条搜索
│   │   │   └── douyin_searcher.py     # 抖音搜索
│   │   ├── persistence/
│   │   │   ├── cookie_redis_store.py  # Cookie 持久化
│   │   │   └── content_repo.py        # 写入内容到 DB
│   │   ├── messaging/
│   │   │   ├── redis_consumer.py      # 消费队列消息
│   │   │   └── redis_publisher.py     # 发布完成事件
│   │   └── container.py
│   ├── worker.py                       # Worker 启动入口（消费循环）
│   ├── main.py                         # FastAPI（仅健康检查）
│   └── config.py
├── tests/
├── Dockerfile
└── requirements.txt
```

**核心职责边界：**
- ✅ 消费 `crawl.requested` 和 `search.requested` 消息
- ✅ 三级浏览器引擎自动降级
- ✅ 各平台文章抓取（公众号、头条）
- ✅ 各平台关键词搜索 + 热度排序
- ✅ Cookie 池管理和登录态维护
- ✅ 爬取完成后写入 DB + 发布 `crawl.completed` 事件
- ❌ 不处理视频、不做转录

---

### 2.3 Media Worker Service

```
services/media-worker/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   └── health.py
│   │   └── schemas/
│   ├── application/
│   │   ├── download_video.py       # 下载视频用例
│   │   ├── extract_audio.py        # 提取音频用例
│   │   ├── transcribe_audio.py     # 转录用例
│   │   └── process_pipeline.py     # 完整流水线编排
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── video_file.py       # 视频文件实体
│   │   │   ├── audio_file.py       # 音频文件实体
│   │   │   └── transcript.py       # 转录结果实体
│   │   ├── ports/
│   │   │   ├── video_downloader.py # 视频下载接口
│   │   │   ├── audio_extractor.py  # 音频提取接口
│   │   │   ├── transcriber.py      # ASR 转录接口
│   │   │   ├── file_storage.py     # 文件存储接口
│   │   │   └── message_consumer.py # 消息消费接口
│   │   ├── value_objects/
│   │   │   ├── transcript_segment.py  # 转录段落 {start, end, text}
│   │   │   └── media_format.py        # 媒体格式
│   │   └── exceptions.py
│   ├── infrastructure/
│   │   ├── downloaders/
│   │   │   ├── douyin_downloader.py       # 抖音视频下载
│   │   │   ├── wechat_video_downloader.py # 微信视频号下载
│   │   │   └── ytdlp_downloader.py        # yt-dlp 兜底
│   │   ├── audio/
│   │   │   └── ffmpeg_extractor.py        # FFmpeg 提取音频
│   │   ├── transcribers/
│   │   │   ├── sensevoice_transcriber.py  # SenseVoice ASR
│   │   │   └── whisper_transcriber.py     # Whisper 备选
│   │   ├── storage/
│   │   │   └── local_file_storage.py      # 本地文件存储
│   │   ├── persistence/
│   │   │   └── content_repo.py            # 更新转录结果到 DB
│   │   ├── messaging/
│   │   │   ├── redis_consumer.py
│   │   │   └── redis_publisher.py
│   │   └── container.py
│   ├── worker.py                           # Worker 启动入口
│   ├── main.py
│   └── config.py
├── tests/
├── Dockerfile
└── requirements.txt
```

**核心职责边界：**
- ✅ 消费 `download.requested` 消息
- ✅ 解析视频真实地址（抖音、视频号）
- ✅ 下载无水印视频
- ✅ FFmpeg 提取音频
- ✅ SenseVoice ASR 逐字转录
- ✅ 保存转录结果到 DB
- ✅ 发布 `transcription.completed` 事件
- ✅ 文件清理（可选自动删除视频）
- ❌ 不爬文章、不做搜索

---

### 2.4 Scheduler Service

```
services/scheduler/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── tasks.py           # CRUD 定时任务（Web App 调用）
│   │   │   └── health.py
│   │   └── schemas/
│   │       └── task.py
│   ├── application/
│   │   ├── manage_task.py         # 任务增删改查用例
│   │   ├── execute_task.py        # 执行单次任务用例
│   │   └── orchestrate_pipeline.py# 编排多步骤流水线
│   ├── domain/
│   │   ├── entities/
│   │   │   ├── scheduled_task.py  # 定时任务实体
│   │   │   ├── pipeline.py        # 流水线实体
│   │   │   └── task_execution.py  # 执行记录实体
│   │   ├── ports/
│   │   │   ├── task_repository.py # 任务持久化接口
│   │   │   ├── message_publisher.py
│   │   │   ├── message_consumer.py
│   │   │   └── clock.py           # 时钟接口（方便测试）
│   │   ├── services/
│   │   │   ├── cron_parser.py     # Cron 表达式解析
│   │   │   ├── deduplication.py   # URL 去重策略
│   │   │   └── retry_policy.py    # 重试策略
│   │   └── exceptions.py
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── task_repo.py       # 任务存储
│   │   │   └── execution_repo.py  # 执行记录存储
│   │   ├── messaging/
│   │   │   ├── redis_publisher.py
│   │   │   └── redis_consumer.py  # 监听完成/失败事件
│   │   ├── scheduling/
│   │   │   └── apscheduler_adapter.py  # APScheduler 定时器
│   │   └── container.py
│   ├── scheduler_loop.py          # 调度主循环
│   ├── main.py
│   └── config.py
├── tests/
├── Dockerfile
└── requirements.txt
```

**核心职责边界：**
- ✅ 定时任务 CRUD（暴露 API 给 Web App 调用）
- ✅ Cron 表达式定时触发
- ✅ 任务编排（搜索 → 爬取 → 下载 → 转录）
- ✅ 监听完成/失败事件，推进流水线状态
- ✅ 失败重试（指数退避，最多 3 次）
- ✅ URL 去重（24h 内不重复采集）
- ❌ 不自己执行任何采集/下载/转录，只发消息让 Worker 做

---

## 三、数据模型设计

### 3.1 PostgreSQL Schema 划分

```sql
-- public schema: 共享数据（多服务可读）
-- crawler schema: Crawler Worker 私有
-- media schema: Media Worker 私有
-- scheduler schema: Scheduler 私有
```

### 3.2 核心表设计

```sql
-- ============================================
-- public.contents — 内容主表（核心）
-- 写入者：Crawler Worker, Media Worker
-- 读取者：所有服务
-- ============================================
CREATE TABLE public.contents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 基础信息
    platform        VARCHAR(20) NOT NULL,   -- wechat_article/toutiao/douyin/wechat_video
    content_type    VARCHAR(10) NOT NULL,   -- article/video
    title           TEXT NOT NULL,
    author          VARCHAR(200),
    source_url      TEXT NOT NULL UNIQUE,
    cover_image_url TEXT,
    
    -- 文章内容
    body_html       TEXT,                   -- 原始 HTML
    body_markdown   TEXT,                   -- 转换后的 Markdown
    body_text       TEXT,                   -- 纯文本（用于搜索）
    
    -- 视频信息
    video_file_path TEXT,
    video_duration  INTEGER,                -- 秒
    
    -- 转录信息
    transcript_text TEXT,                   -- 转录全文
    transcript_segments JSONB,              -- [{start_ms, end_ms, text}]
    transcript_status VARCHAR(20),          -- null/pending/processing/completed/failed
    
    -- 热度指标
    likes_count     INTEGER DEFAULT 0,
    reads_count     INTEGER DEFAULT 0,
    shares_count    INTEGER DEFAULT 0,
    comments_count  INTEGER DEFAULT 0,
    hot_score       FLOAT DEFAULT 0,
    
    -- 用户操作
    tags            TEXT[] DEFAULT '{}',
    is_favorited    BOOLEAN DEFAULT FALSE,
    user_notes      TEXT,                   -- 用户备注
    
    -- 状态
    status          VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending → crawling → downloaded → transcribing → completed
    -- 任何阶段都可能 → failed
    error_message   TEXT,
    
    -- 时间
    published_at    TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_contents_platform ON public.contents(platform);
CREATE INDEX idx_contents_status ON public.contents(status);
CREATE INDEX idx_contents_hot_score ON public.contents(hot_score DESC);
CREATE INDEX idx_contents_created_at ON public.contents(created_at DESC);
CREATE INDEX idx_contents_tags ON public.contents USING GIN(tags);
CREATE INDEX idx_contents_fulltext ON public.contents 
    USING GIN(to_tsvector('simple', coalesce(title,'') || ' ' || coalesce(body_text,'')));


-- ============================================
-- public.notifications — 通知表
-- 写入者：所有服务
-- 读取者：Web App
-- ============================================
CREATE TABLE public.notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type        VARCHAR(30) NOT NULL,       -- crawl_completed/transcription_completed/task_failed
    title       TEXT NOT NULL,
    message     TEXT,
    metadata    JSONB DEFAULT '{}',          -- 关联的 content_id, task_id 等
    is_read     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_notifications_unread ON public.notifications(is_read, created_at DESC);


-- ============================================
-- scheduler.scheduled_tasks — 定时任务表
-- 写入者：Scheduler
-- 读取者：Scheduler, Web App
-- ============================================
CREATE TABLE scheduler.scheduled_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 任务定义
    name            VARCHAR(200) NOT NULL,
    keyword         TEXT NOT NULL,
    platforms       TEXT[] NOT NULL,         -- ['douyin', 'wechat_article']
    content_types   TEXT[] NOT NULL,         -- ['article', 'video']
    max_results     INTEGER DEFAULT 10,     -- 每次最多采集数
    
    -- 调度配置
    cron_expression VARCHAR(50) NOT NULL,    -- "0 8 * * *" 每天早8点
    is_active       BOOLEAN DEFAULT TRUE,
    
    -- 运行状态
    last_run_at     TIMESTAMP WITH TIME ZONE,
    last_run_status VARCHAR(20),            -- success/partial_failure/failed
    next_run_at     TIMESTAMP WITH TIME ZONE,
    total_runs      INTEGER DEFAULT 0,
    
    -- 时间
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ============================================
-- scheduler.task_executions — 任务执行记录
-- ============================================
CREATE TABLE scheduler.task_executions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID REFERENCES scheduler.scheduled_tasks(id),
    
    -- 执行信息
    trigger_type    VARCHAR(20) NOT NULL,    -- scheduled/manual
    status          VARCHAR(20) NOT NULL,    -- running/completed/failed
    
    -- 结果统计
    total_items     INTEGER DEFAULT 0,
    success_items   INTEGER DEFAULT 0,
    failed_items    INTEGER DEFAULT 0,
    
    -- 详细记录
    items           JSONB DEFAULT '[]',      -- [{url, status, content_id, error}]
    error_message   TEXT,
    
    -- 时间
    started_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at    TIMESTAMP WITH TIME ZONE
);


-- ============================================
-- crawler.cookie_sessions — Cookie 会话存储
-- 写入者：Crawler Worker
-- 读取者：Crawler Worker
-- ============================================
CREATE TABLE crawler.cookie_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform        VARCHAR(20) NOT NULL,
    cookies         JSONB NOT NULL,          -- Cookie 数据
    user_agent      TEXT,
    is_valid        BOOLEAN DEFAULT TRUE,
    last_used_at    TIMESTAMP WITH TIME ZONE,
    expires_at      TIMESTAMP WITH TIME ZONE,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);


-- ============================================
-- media.file_records — 文件记录
-- 写入者：Media Worker
-- 读取者：Media Worker, Web App
-- ============================================
CREATE TABLE media.file_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id      UUID REFERENCES public.contents(id),
    
    file_type       VARCHAR(20) NOT NULL,    -- video/audio/export
    file_path       TEXT NOT NULL,
    file_size_bytes BIGINT,
    mime_type       VARCHAR(100),
    duration_ms     INTEGER,
    
    -- 状态
    status          VARCHAR(20) DEFAULT 'active',  -- active/deleted
    deleted_at      TIMESTAMP WITH TIME ZONE,
    
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 3.3 实体关系图

```
┌─────────────────┐       ┌──────────────────┐
│   contents      │───1:N─│  file_records    │
│                 │       │  (视频/音频文件)  │
└────────┬────────┘       └──────────────────┘
         │
         │ 1:N (通过 metadata.content_id)
         │
┌────────▼────────┐       ┌──────────────────┐
│  notifications  │       │ scheduled_tasks  │
│                 │       │                  │
└─────────────────┘       └────────┬─────────┘
                                   │ 1:N
                          ┌────────▼─────────┐
                          │ task_executions  │
                          └──────────────────┘
```

---

## 四、API 接口设计

### 4.1 Web App 对外 API（前端调用）

#### 内容管理

```yaml
GET /api/v1/contents
  description: 获取内容列表（分页、筛选、排序）
  params:
    page: int = 1
    page_size: int = 20
    platform: string? (wechat_article|toutiao|douyin|wechat_video)
    content_type: string? (article|video)
    status: string? (pending|completed|failed)
    is_favorited: bool?
    tags: string[]?
    keyword: string?           # 全文搜索
    sort_by: string = "created_at"  # created_at|hot_score|published_at
    sort_order: string = "desc"
  response:
    total: int
    items: Content[]

GET /api/v1/contents/{id}
  description: 获取内容详情（含转录全文）
  response: ContentDetail

PUT /api/v1/contents/{id}
  description: 更新内容（编辑转录文本、标签、备注）
  body:
    transcript_text: string?
    tags: string[]?
    user_notes: string?
    is_favorited: bool?
  response: ContentDetail

DELETE /api/v1/contents/{id}
  description: 删除内容
  response: 204
```

#### 采集操作

```yaml
POST /api/v1/crawl/url
  description: 通过 URL 采集内容
  body:
    url: string (required)
  response:
    task_id: string
    status: "queued"
    platform: string (自动识别)
    content_type: string (自动识别)

POST /api/v1/crawl/search
  description: 关键词搜索热门内容
  body:
    keyword: string (required)
    platforms: string[] = ["wechat_article", "toutiao", "douyin", "wechat_video"]
    limit: int = 20
  response:
    task_id: string
    status: "queued"

POST /api/v1/crawl/batch
  description: 批量采集（多个 URL）
  body:
    urls: string[] (required, max 50)
  response:
    task_id: string
    total: int
    status: "queued"
```

#### 导出

```yaml
POST /api/v1/contents/{id}/export
  description: 导出内容为文件
  body:
    format: string (required) — "markdown" | "word" | "pdf"
  response:
    file_url: string           # 下载地址
    filename: string
    expires_at: datetime       # 链接过期时间
```

#### 定时任务

```yaml
GET /api/v1/tasks
  description: 获取定时任务列表
  response: ScheduledTask[]

POST /api/v1/tasks
  description: 创建定时任务
  body:
    name: string
    keyword: string
    platforms: string[]
    content_types: string[]
    cron_expression: string
    max_results: int = 10
  response: ScheduledTask

PUT /api/v1/tasks/{id}
  description: 修改定时任务
  body: (同上，全部 optional)
  response: ScheduledTask

DELETE /api/v1/tasks/{id}
  description: 删除定时任务
  response: 204

POST /api/v1/tasks/{id}/run
  description: 手动触发执行
  response:
    execution_id: string
    status: "running"

GET /api/v1/tasks/{id}/executions
  description: 获取执行历史
  response: TaskExecution[]
```

#### 通知

```yaml
GET /api/v1/notifications
  description: 获取通知列表
  params:
    is_read: bool?
    page: int = 1
    page_size: int = 50
  response:
    unread_count: int
    items: Notification[]

PUT /api/v1/notifications/{id}/read
  description: 标记已读
  response: 204

PUT /api/v1/notifications/read-all
  description: 全部标记已读
  response: 204
```

#### 设置

```yaml
GET /api/v1/settings/scoring-weights
  description: 获取热度排序权重
  response:
    wechat_article: {likes: 0.5, reads: 0.3, shares: 0.2}
    toutiao: {likes: 0.5, reads: 0.3, shares: 0.2}
    douyin: {likes: 0.5, views: 0.3, shares: 0.2}
    wechat_video: {likes: 0.5, views: 0.3, shares: 0.2}

PUT /api/v1/settings/scoring-weights
  description: 更新热度排序权重
  body: (同上)
  response: 200
```

### 4.2 WebSocket 接口

```yaml
WS /ws/notifications
  description: 实时推送通知
  events:
    - type: "crawl.completed"
      data: {content_id, title, platform}
    - type: "transcription.completed"
      data: {content_id, title}
    - type: "task.completed"
      data: {task_id, execution_id, success_count, fail_count}
    - type: "error"
      data: {message, detail}
```

### 4.3 服务内部 API（仅健康检查）

```yaml
# 每个 Worker 暴露
GET /health
  response:
    status: "healthy" | "degraded" | "unhealthy"
    version: string
    uptime_seconds: int
    details:
      queue_lag: int           # 队列积压数量
      active_tasks: int        # 正在处理的任务数
```

---

## 五、消息队列设计

### 5.1 Redis Streams 结构

```
Stream Name                    | 生产者           | 消费者           | 含义
───────────────────────────────┼─────────────────┼─────────────────┼──────────────
crawl:article:requested        | Web App         | Crawler Worker  | 请求爬取文章
crawl:search:requested         | Web App/Sched   | Crawler Worker  | 请求搜索
crawl:article:completed        | Crawler Worker  | Web App/Sched   | 文章爬取完成
crawl:article:failed           | Crawler Worker  | Scheduler       | 文章爬取失败

media:download:requested       | Web App/Sched   | Media Worker    | 请求下载视频
media:download:completed       | Media Worker    | Scheduler       | 下载完成
media:transcription:completed  | Media Worker    | Web App         | 转录完成
media:pipeline:failed          | Media Worker    | Scheduler       | 流水线失败

notification:send              | 所有 Worker     | Web App         | 通知推送
```

### 5.2 消息格式规范

```python
# 所有消息统一格式
{
    "message_id": "uuid",           # 消息唯一 ID
    "timestamp": "ISO8601",         # 发送时间
    "source": "crawler-worker",     # 来源服务
    "correlation_id": "uuid",       # 关联 ID（追踪整条链路）
    "payload": {                    # 业务数据
        ...
    }
}
```

### 5.3 消息定义详细

```python
# === crawl:article:requested ===
{
    "message_id": "...",
    "timestamp": "2026-06-10T10:00:00Z",
    "source": "web-app",
    "correlation_id": "task-uuid",
    "payload": {
        "content_id": "uuid",       # 预创建的 content 记录 ID
        "url": "https://mp.weixin.qq.com/s/...",
        "platform": "wechat_article",
        "priority": "normal"        # normal/high
    }
}

# === crawl:article:completed ===
{
    "message_id": "...",
    "timestamp": "...",
    "source": "crawler-worker",
    "correlation_id": "task-uuid",
    "payload": {
        "content_id": "uuid",
        "title": "文章标题",
        "author": "作者",
        "platform": "wechat_article",
        "metrics": {
            "likes": 1234,
            "reads": 50000,
            "shares": 200
        }
    }
}

# === media:download:requested ===
{
    "message_id": "...",
    "timestamp": "...",
    "source": "web-app",
    "correlation_id": "task-uuid",
    "payload": {
        "content_id": "uuid",
        "url": "https://www.douyin.com/video/...",
        "platform": "douyin",
        "need_transcription": true   # 下载后是否自动转录
    }
}

# === media:transcription:completed ===
{
    "message_id": "...",
    "timestamp": "...",
    "source": "media-worker",
    "correlation_id": "task-uuid",
    "payload": {
        "content_id": "uuid",
        "transcript_text": "完整转录文本...",
        "duration_ms": 180000,
        "segments_count": 45,
        "language": "zh"
    }
}
```

### 5.4 消费者组设计

```python
# 每个 Worker 使用 Consumer Group 确保消息不丢失
# 即使 Worker 重启，未 ACK 的消息会重新投递

CONSUMER_GROUPS = {
    "crawl:article:requested": {
        "group": "crawler-workers",
        "consumers": ["crawler-1"]      # 可以多实例
    },
    "media:download:requested": {
        "group": "media-workers",
        "consumers": ["media-1"]
    },
    "notification:send": {
        "group": "web-app-notifiers",
        "consumers": ["web-1"]
    }
}
```

---

## 六、三级浏览器引擎设计

### 6.1 接口定义（Port）

```python
# services/crawler/app/domain/ports/browser_engine.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class EngineLevel(Enum):
    L1_DRISSION = 1
    L2_PLAYWRIGHT = 2
    L3_BROWSER_USE = 3


@dataclass
class BrowseResult:
    """浏览器引擎返回的统一结果"""
    is_success: bool
    html_content: str = ""
    status_code: int = 0
    engine_used: EngineLevel = EngineLevel.L1_DRISSION
    error_message: str = ""
    elapsed_ms: int = 0


class BrowserEngine(ABC):
    """浏览器引擎接口"""
    
    @property
    @abstractmethod
    def level(self) -> EngineLevel:
        pass
    
    @abstractmethod
    async def fetch_page(self, url: str, wait_selector: str = None) -> BrowseResult:
        """获取页面内容"""
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        """检查引擎是否可用"""
        pass
```

### 6.2 降级策略（Domain Service）

```python
# services/crawler/app/domain/services/engine_fallback.py

from dataclasses import dataclass


@dataclass
class FallbackTrigger:
    """降级触发条件"""
    http_error_codes: list[int] = (403, 429, 503)
    captcha_keywords: list[str] = ("captcha", "verify", "验证", "滑块")
    empty_content_min_length: int = 100
    max_retries_per_engine: int = 2


class EngineFallbackStrategy:
    """引擎降级决策逻辑"""
    
    def __init__(self, trigger_config: FallbackTrigger):
        self.config = trigger_config
    
    def should_fallback(self, result: BrowseResult) -> bool:
        """判断是否需要降级到下一级引擎"""
        if result.status_code in self.config.http_error_codes:
            return True
        if self._contains_captcha(result.html_content):
            return True
        if len(result.html_content) < self.config.empty_content_min_length:
            return True
        return False
    
    def _contains_captcha(self, html: str) -> bool:
        return any(kw in html.lower() for kw in self.config.captcha_keywords)
    
    def get_platform_start_level(self, platform: str) -> EngineLevel:
        """不同平台的起始引擎级别"""
        platform_levels = {
            "wechat_article": EngineLevel.L1_DRISSION,
            "toutiao": EngineLevel.L1_DRISSION,
            "douyin": EngineLevel.L2_PLAYWRIGHT,
            "wechat_video": EngineLevel.L2_PLAYWRIGHT,
        }
        return platform_levels.get(platform, EngineLevel.L1_DRISSION)
```

### 6.3 智能浏览器适配器（Infrastructure）

```python
# services/crawler/app/infrastructure/browser/smart_browser.py

import logging
from domain.ports.browser_engine import BrowserEngine, BrowseResult, EngineLevel
from domain.services.engine_fallback import EngineFallbackStrategy

logger = logging.getLogger(__name__)


class SmartBrowser:
    """智能浏览器 — 自动降级"""
    
    def __init__(
        self,
        engines: dict[EngineLevel, BrowserEngine],
        fallback_strategy: EngineFallbackStrategy
    ):
        self._engines = engines
        self._strategy = fallback_strategy
    
    async def fetch(self, url: str, platform: str, wait_selector: str = None) -> BrowseResult:
        start_level = self._strategy.get_platform_start_level(platform)
        
        for level in EngineLevel:
            if level.value < start_level.value:
                continue
            
            engine = self._engines.get(level)
            if engine is None or not await engine.is_available():
                continue
            
            for attempt in range(self._strategy.config.max_retries_per_engine):
                result = await engine.fetch_page(url, wait_selector)
                
                if result.is_success and not self._strategy.should_fallback(result):
                    logger.info(
                        "页面获取成功",
                        extra={"url": url, "engine": level.name, "attempt": attempt + 1}
                    )
                    return result
                
                logger.warning(
                    "引擎未成功获取页面",
                    extra={
                        "url": url,
                        "engine": level.name,
                        "attempt": attempt + 1,
                        "status": result.status_code,
                        "will_retry": attempt < self._strategy.config.max_retries_per_engine - 1
                    }
                )
            
            logger.warning("引擎降级", extra={"from": level.name, "url": url})
        
        return BrowseResult(
            is_success=False,
            error_message="所有引擎均无法获取页面",
            engine_used=EngineLevel.L3_BROWSER_USE
        )
```

---

## 七、各平台爬虫设计

### 7.1 爬虫接口定义

```python
# services/crawler/app/domain/ports/article_crawler.py

from abc import ABC, abstractmethod
from domain.entities.crawl_result import CrawlResult


class ArticleCrawler(ABC):
    """文章爬虫接口"""
    
    @abstractmethod
    async def crawl(self, url: str) -> CrawlResult:
        """抓取单篇文章"""
        pass
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断该爬虫是否能处理此 URL"""
        pass
```

```python
# services/crawler/app/domain/ports/content_searcher.py

from abc import ABC, abstractmethod
from domain.entities.search_result import SearchResult


class ContentSearcher(ABC):
    """内容搜索接口"""
    
    @abstractmethod
    async def search(self, keyword: str, limit: int = 20) -> list[SearchResult]:
        """按关键词搜索"""
        pass
    
    @property
    @abstractmethod
    def platform(self) -> str:
        pass
```

### 7.2 微信公众号爬虫设计

```python
# services/crawler/app/infrastructure/crawlers/wechat_article.py

"""
微信公众号文章抓取策略：
1. 公众号文章链接格式：https://mp.weixin.qq.com/s/...
2. 文章页面是服务端渲染，可以直接 HTTP 请求获取 HTML
3. 正文在 <div id="js_content"> 中
4. 图片有防盗链（Referer 检查），需要代理下载
5. 阅读量/点赞等数据需要额外 API 请求（需登录态）
"""

class WechatArticleCrawler(ArticleCrawler):
    
    URL_PATTERN = r"mp\.weixin\.qq\.com/s"
    
    def can_handle(self, url: str) -> bool:
        return bool(re.search(self.URL_PATTERN, url))
    
    async def crawl(self, url: str) -> CrawlResult:
        # 1. 通过 SmartBrowser 获取页面
        browse_result = await self._browser.fetch(url, platform="wechat_article")
        
        if not browse_result.is_success:
            raise CrawlFailedError(url=url, reason=browse_result.error_message)
        
        # 2. 解析 HTML 提取内容
        article = self._parse_article(browse_result.html_content)
        
        # 3. 获取指标数据（需要登录态）
        metrics = await self._fetch_metrics(url)
        
        return CrawlResult(
            title=article.title,
            author=article.author,
            body_html=article.body_html,
            body_markdown=self._html_to_markdown(article.body_html),
            published_at=article.publish_time,
            metrics=metrics
        )
```

### 7.3 今日头条爬虫设计

```python
# services/crawler/app/infrastructure/crawlers/toutiao_article.py

"""
今日头条文章抓取策略：
1. 文章链接格式：https://www.toutiao.com/article/... 或 https://m.toutiao.com/...
2. 页面 CSR 渲染，需要浏览器执行 JS
3. 文章数据在页面 script 标签的 JSON 中（__INITIAL_STATE__）
4. 也可通过 API 接口获取：https://www.toutiao.com/api/pc/feed/...
5. 反爬较强：需要 Cookie + 签名
"""

class ToutiaoArticleCrawler(ArticleCrawler):
    
    URL_PATTERN = r"toutiao\.com/(article|a\d+)"
    
    async def crawl(self, url: str) -> CrawlResult:
        # 优先尝试 API 方式（L1 DrissionPage 够用）
        article_id = self._extract_article_id(url)
        api_result = await self._try_api_fetch(article_id)
        
        if api_result:
            return api_result
        
        # API 失败则用浏览器渲染
        browse_result = await self._browser.fetch(
            url, 
            platform="toutiao",
            wait_selector="#article-content"
        )
        return self._parse_rendered_page(browse_result.html_content)
```

### 7.4 平台 URL 识别器

```python
# services/crawler/app/domain/services/platform_detector.py

import re
from domain.value_objects.platform import Platform, ContentType


PLATFORM_PATTERNS = {
    Platform.WECHAT_ARTICLE: {
        "pattern": r"mp\.weixin\.qq\.com/s",
        "content_type": ContentType.ARTICLE
    },
    Platform.TOUTIAO: {
        "pattern": r"toutiao\.com/(article|a\d+)",
        "content_type": ContentType.ARTICLE
    },
    Platform.DOUYIN: {
        "pattern": r"(douyin\.com|iesdouyin\.com)",
        "content_type": ContentType.VIDEO
    },
    Platform.WECHAT_VIDEO: {
        "pattern": r"(channels\.weixin\.qq\.com|finder\.video\.qq\.com)",
        "content_type": ContentType.VIDEO
    },
}


def detect_platform(url: str) -> tuple[Platform, ContentType]:
    """根据 URL 自动识别平台和内容类型"""
    for platform, config in PLATFORM_PATTERNS.items():
        if re.search(config["pattern"], url):
            return platform, config["content_type"]
    raise PlatformNotSupportedError(url=url)
```

---

## 八、视频下载与转录流水线

### 8.1 流水线流程

```
┌──────────────────────────────────────────────────────────────────┐
│                  Media Worker Pipeline                            │
│                                                                  │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌────────────┐  │
│  │ 解析URL │───→│ 下载视频 │───→│提取音频 │───→│ ASR 转录   │  │
│  │         │    │ (无水印) │    │ (FFmpeg)│    │(SenseVoice)│  │
│  └─────────┘    └──────────┘    └─────────┘    └────────────┘  │
│       │              │               │               │          │
│       ▼              ▼               ▼               ▼          │
│  video_url      video.mp4        audio.wav      transcript     │
│                                                                  │
│  耗时: ~2s        ~10-60s          ~3s           ~30-120s       │
└──────────────────────────────────────────────────────────────────┘
```

### 8.2 下载器接口

```python
# services/media-worker/app/domain/ports/video_downloader.py

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class VideoInfo:
    """解析后的视频信息"""
    title: str
    author: str
    download_url: str           # 真实下载地址
    duration_ms: int
    cover_url: str
    metrics: dict               # {likes, views, shares, comments}


@dataclass  
class DownloadResult:
    """下载结果"""
    file_path: str
    file_size_bytes: int
    duration_ms: int
    resolution: str             # "1080p" / "720p"


class VideoDownloader(ABC):
    """视频下载器接口"""
    
    @abstractmethod
    async def parse_video_info(self, url: str) -> VideoInfo:
        """解析视频信息（不下载）"""
        pass
    
    @abstractmethod
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """下载视频到本地"""
        pass
    
    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """判断是否能处理此 URL"""
        pass
```

### 8.3 转录器接口

```python
# services/media-worker/app/domain/ports/transcriber.py

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptSegment:
    """转录片段"""
    start_ms: int               # 开始时间（毫秒）
    end_ms: int                 # 结束时间（毫秒）
    text: str                   # 文本内容


@dataclass
class TranscriptionResult:
    """转录结果"""
    full_text: str              # 完整文本（一字不落）
    segments: list[TranscriptSegment]   # 带时间戳的分段
    language: str               # 识别到的语言
    duration_ms: int            # 音频总时长
    confidence: float           # 置信度 0-1


class Transcriber(ABC):
    """语音转文字接口"""
    
    @abstractmethod
    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        """转录音频文件"""
        pass
    
    @abstractmethod
    async def is_model_loaded(self) -> bool:
        """模型是否已加载"""
        pass
```

### 8.4 SenseVoice 实现设计

```python
# services/media-worker/app/infrastructure/transcribers/sensevoice_transcriber.py

"""
SenseVoice 集成要点：
1. 模型加载一次，常驻内存（~2.5GB）
2. 支持 VAD（语音活动检测）自动分段
3. 支持中文标点恢复
4. 长音频自动切片处理（每片 30s）
5. 输出带时间戳的逐句结果
"""

class SenseVoiceTranscriber(Transcriber):
    
    SUPPORTED_FORMATS = (".wav", ".mp3", ".flac", ".m4a")
    MAX_AUDIO_DURATION_MS = 3600000   # 最长 1 小时
    CHUNK_DURATION_MS = 30000          # 每片 30 秒
    
    def __init__(self, model_path: str):
        self._model_path = model_path
        self._model = None
    
    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        if not self._model:
            await self._load_model()
        
        # 1. 检查音频格式和时长
        audio_info = await self._validate_audio(audio_path)
        
        # 2. VAD 分段
        segments = await self._vad_segment(audio_path)
        
        # 3. 逐段识别
        results = []
        for segment in segments:
            text = await self._recognize_segment(segment)
            results.append(TranscriptSegment(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                text=text
            ))
        
        # 4. 合并为完整文本
        full_text = "".join(seg.text for seg in results)
        
        return TranscriptionResult(
            full_text=full_text,
            segments=results,
            language="zh",
            duration_ms=audio_info.duration_ms,
            confidence=0.95
        )
```

### 8.5 音频提取器

```python
# services/media-worker/app/infrastructure/audio/ffmpeg_extractor.py

"""
FFmpeg 音频提取：
- 输入：任意视频格式
- 输出：16kHz 单声道 WAV（SenseVoice 最优输入格式）
- 命令：ffmpeg -i input.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 output.wav
"""

class FFmpegAudioExtractor(AudioExtractor):
    
    OUTPUT_SAMPLE_RATE = 16000
    OUTPUT_CHANNELS = 1
    OUTPUT_FORMAT = "wav"
    
    async def extract(self, video_path: str, output_dir: str) -> str:
        output_path = self._generate_output_path(video_path, output_dir)
        
        command = [
            "ffmpeg", "-i", video_path,
            "-vn",                          # 不要视频
            "-acodec", "pcm_s16le",         # 16-bit PCM
            "-ar", str(self.OUTPUT_SAMPLE_RATE),  # 16kHz
            "-ac", str(self.OUTPUT_CHANNELS),     # 单声道
            "-y",                           # 覆盖已有文件
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise AudioExtractionError(
                video_path=video_path,
                reason=stderr.decode()
            )
        
        return output_path
```

---

## 九、热度排序算法设计

### 9.1 算法实现

```python
# services/crawler/app/domain/services/scoring.py

from dataclasses import dataclass
from datetime import datetime, timezone
import math


@dataclass
class ScoringWeights:
    """可配置的评分权重"""
    likes_weight: float = 0.5
    reads_weight: float = 0.3
    shares_weight: float = 0.2
    time_decay_halflife_days: float = 7.0


class HotScoreCalculator:
    """热度评分计算器"""
    
    def __init__(self, weights_by_platform: dict[str, ScoringWeights]):
        self._weights = weights_by_platform
    
    def calculate(
        self,
        platform: str,
        likes: int,
        reads: int,
        shares: int,
        published_at: datetime
    ) -> float:
        weights = self._weights.get(platform, ScoringWeights())
        
        # 对数归一化（避免大号碾压小号）
        norm_likes = self._log_normalize(likes)
        norm_reads = self._log_normalize(reads)
        norm_shares = self._log_normalize(shares)
        
        # 加权综合分
        raw_score = (
            norm_likes * weights.likes_weight +
            norm_reads * weights.reads_weight +
            norm_shares * weights.shares_weight
        )
        
        # 时间衰减
        days_old = self._days_since(published_at)
        decay = self._time_decay(days_old, weights.time_decay_halflife_days)
        
        return round(raw_score * decay, 4)
    
    def _log_normalize(self, value: int) -> float:
        """对数归一化：log(1 + value)"""
        return math.log1p(max(0, value))
    
    def _days_since(self, dt: datetime) -> float:
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).total_seconds() / 86400)
    
    def _time_decay(self, days_old: float, halflife: float) -> float:
        """半衰期衰减：7 天后热度降为一半"""
        return 0.5 ** (days_old / halflife)
```

### 9.2 权重配置存储

```python
# 权重存储在 Redis 中，支持动态调整无需重启
# Key: scoring:weights:{platform}
# Value: JSON {likes_weight, reads_weight, shares_weight, time_decay_halflife_days}
```

---

## 十、导出模块设计

### 10.1 导出器接口

```python
# services/web-app/app/domain/ports/exporter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from domain.value_objects.export_format import ExportFormat


@dataclass
class ExportResult:
    file_path: str
    filename: str
    mime_type: str
    file_size_bytes: int


class ContentExporter(ABC):
    
    @property
    @abstractmethod
    def format(self) -> ExportFormat:
        pass
    
    @abstractmethod
    async def export(self, content: Content) -> ExportResult:
        pass
```

### 10.2 导出内容模板

```
# Markdown 导出模板
---
title: {title}
author: {author}
platform: {platform}
date: {published_at}
source: {source_url}
---

# {title}

**作者**: {author}  
**发布时间**: {published_at}  
**平台**: {platform}  

---

{body_markdown 或 transcript_text}

---

## 指标

- 点赞: {likes_count}
- 阅读: {reads_count}
- 转发: {shares_count}
```

### 10.3 Word 导出结构

```python
# 使用 python-docx
# 结构：标题 → 元信息表格 → 正文 → 指标
```

### 10.4 PDF 导出

```python
# 方案：先生成 HTML → WeasyPrint 转 PDF
# 支持中文字体（思源黑体 / Noto Sans CJK）
```

---

## 十一、定时调度设计

### 11.1 调度器核心逻辑

```python
# services/scheduler/app/infrastructure/scheduling/apscheduler_adapter.py

"""
使用 APScheduler 实现定时触发：
- 启动时从 DB 加载所有 active 任务
- 根据 cron_expression 注册触发器
- 触发时发消息到队列
- 支持动态添加/删除/修改任务
"""
```

### 11.2 任务编排状态机

```python
# services/scheduler/app/domain/entities/pipeline.py

"""
Pipeline 状态机：

              ┌──────────────────────────────────────┐
              │                                      │
    ┌─────────▼──┐     ┌──────────┐     ┌─────────┐│    ┌───────────┐
    │  searching │────→│downloading│────→│transcri-││───→│ completed │
    └────────────┘     └──────────┘     │ bing    ││    └───────────┘
         │                  │           └─────────┘│
         │                  │                │     │
         ▼                  ▼                ▼     │
    ┌─────────────────────────────────────────┐    │
    │              failed                      │←──┘
    │  (记录失败原因，可重试)                   │
    └──────────────────────────────────────────┘
"""

class PipelineState(Enum):
    CREATED = "created"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    COMPLETED = "completed"
    FAILED = "failed"
```

### 11.3 去重策略

```python
# services/scheduler/app/domain/services/deduplication.py

class DeduplicationStrategy:
    """URL 去重：相同 URL 在窗口期内不重复采集"""
    
    DEDUP_WINDOW_HOURS = 24
    
    async def is_duplicate(self, url: str) -> bool:
        """检查 Redis 中是否已存在"""
        key = f"dedup:{self._hash_url(url)}"
        return await self._redis.exists(key)
    
    async def mark_processed(self, url: str):
        """标记已处理，设置 TTL"""
        key = f"dedup:{self._hash_url(url)}"
        await self._redis.setex(key, self.DEDUP_WINDOW_HOURS * 3600, "1")
```

### 11.4 重试策略

```python
# services/scheduler/app/domain/services/retry_policy.py

class ExponentialBackoffRetry:
    """指数退避重试"""
    
    MAX_RETRIES = 3
    BASE_DELAY_SECONDS = 60         # 第 1 次重试等 1 分钟
    MAX_DELAY_SECONDS = 3600        # 最长等 1 小时
    
    def get_next_retry_delay(self, attempt: int) -> int:
        """计算下次重试延迟（秒）"""
        delay = self.BASE_DELAY_SECONDS * (2 ** attempt)
        return min(delay, self.MAX_DELAY_SECONDS)
    
    def should_retry(self, attempt: int, error_type: str) -> bool:
        """判断是否应该重试"""
        if attempt >= self.MAX_RETRIES:
            return False
        # 不可重试的错误
        non_retryable = ["platform_not_supported", "invalid_url"]
        return error_type not in non_retryable
```

---

## 十二、通知系统设计

### 12.1 通知流程

```
Worker 完成任务
    → 发消息到 notification:send Stream
    → Web App 消费该消息
    → 写入 notifications 表
    → 通过 WebSocket 实时推送到前端
    → 前端显示小红点 + Toast 提醒
```

### 12.2 WebSocket 管理

```python
# services/web-app/app/infrastructure/realtime/websocket_notifier.py

class WebSocketManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        self._connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self._connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        self._connections.remove(websocket)
    
    async def broadcast(self, event_type: str, data: dict):
        """广播通知到所有连接"""
        message = {"type": event_type, "data": data, "timestamp": now_iso()}
        dead_connections = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except WebSocketDisconnect:
                dead_connections.append(ws)
        for ws in dead_connections:
            self._connections.remove(ws)
```

### 12.3 通知类型定义

```python
class NotificationType(Enum):
    CRAWL_COMPLETED = "crawl_completed"             # 文章采集完成
    TRANSCRIPTION_COMPLETED = "transcription_completed"  # 转录完成
    TASK_EXECUTION_DONE = "task_execution_done"     # 定时任务执行完毕
    CRAWL_FAILED = "crawl_failed"                   # 采集失败
    PIPELINE_FAILED = "pipeline_failed"             # 流水线失败
```

---

## 十三、配置管理设计

### 13.1 配置文件结构

```yaml
# config/app.yaml — 主配置
app:
  name: ContentHarvester
  version: 1.0.0
  debug: false

database:
  host: postgres
  port: 5432
  name: content_harvester
  user: harvester
  pool_size: 10
  max_overflow: 5

redis:
  host: redis
  port: 6379
  db: 0
  
file_storage:
  base_path: /data/files
  max_file_age_days: 30         # 30 天自动清理
  auto_cleanup: true
```

```yaml
# config/browser_engines.yaml — 浏览器引擎配置
engines:
  drission:
    enabled: true
    timeout_seconds: 15
    max_retries: 2
    
  playwright:
    enabled: true
    timeout_seconds: 30
    max_retries: 2
    headless: true
    browser: chromium
    stealth: true
    
  browser_use:
    enabled: true
    timeout_seconds: 60
    max_retries: 1
    llm_provider: deepseek
    llm_model: deepseek-chat
    max_steps: 15

platforms:
  wechat_article:
    start_engine: drission
    rate_limit_per_minute: 10
  toutiao:
    start_engine: drission
    rate_limit_per_minute: 15
  douyin:
    start_engine: playwright
    rate_limit_per_minute: 8
  wechat_video:
    start_engine: playwright
    rate_limit_per_minute: 8
```

```yaml
# config/scoring.yaml — 热度排序配置
weights:
  wechat_article:
    likes: 0.5
    reads: 0.3
    shares: 0.2
    time_decay_halflife_days: 7
  toutiao:
    likes: 0.5
    reads: 0.3
    shares: 0.2
    time_decay_halflife_days: 5
  douyin:
    likes: 0.5
    views: 0.3
    shares: 0.2
    time_decay_halflife_days: 3
  wechat_video:
    likes: 0.5
    views: 0.3
    shares: 0.2
    time_decay_halflife_days: 5
```

### 13.2 环境变量（敏感信息）

```bash
# .env
DEEPSEEK_API_KEY=sk-xxx
DB_PASSWORD=xxx
REDIS_PASSWORD=
SECRET_KEY=xxx                  # JWT/签名用
```

### 13.3 配置加载优先级

```
环境变量 > .env 文件 > config/*.yaml > 代码默认值
```

---

## 十四、错误处理与容错设计

### 14.1 异常层级

```python
# shared/exceptions.py

class ContentHarvesterError(Exception):
    """全局基类"""
    def __init__(self, message: str, **context):
        self.message = message
        self.context = context
        super().__init__(message)

# === 领域异常 ===
class CrawlError(ContentHarvesterError): pass
class DownloadError(ContentHarvesterError): pass
class TranscriptionError(ContentHarvesterError): pass
class SchedulerError(ContentHarvesterError): pass

# === 具体异常 ===
class PlatformNotSupportedError(CrawlError): pass
class AllEnginesFailedError(CrawlError): pass
class CaptchaRequiredError(CrawlError): pass
class RateLimitedError(CrawlError): pass
class CookieExpiredError(CrawlError): pass

class VideoNotFoundError(DownloadError): pass
class VideoTooLargeError(DownloadError): pass

class AudioTooLongError(TranscriptionError): pass
class ModelNotLoadedError(TranscriptionError): pass
```

### 14.2 API 层统一异常处理

```python
# services/web-app/app/api/middleware.py

@app.exception_handler(ContentHarvesterError)
async def domain_exception_handler(request, exc):
    status_map = {
        PlatformNotSupportedError: 400,
        CookieExpiredError: 401,
        RateLimitedError: 429,
        AllEnginesFailedError: 503,
    }
    status = status_map.get(type(exc), 500)
    return JSONResponse(
        status_code=status,
        content={
            "error": type(exc).__name__,
            "message": exc.message,
            "detail": exc.context
        }
    )
```

### 14.3 Worker 容错

```python
# 每个 Worker 的消费循环都包含：
async def safe_consume_loop():
    while True:
        try:
            message = await queue.read_next(timeout_ms=5000)
            if message:
                await process_message(message)
                await queue.acknowledge(message)
        except RetryableError as e:
            logger.warning("可重试错误", extra={"error": str(e)})
            await queue.nack(message)            # 消息回队列
            await asyncio.sleep(backoff_delay)
        except NonRetryableError as e:
            logger.error("不可重试错误", extra={"error": str(e)})
            await queue.acknowledge(message)     # 不再重试
            await publish_failure_event(message, e)
        except Exception as e:
            logger.critical("未预期异常", extra={"error": str(e)})
            await asyncio.sleep(10)             # 避免死循环
```

---

## 十五、部署设计

### 15.1 Docker Compose（完整版）

```yaml
version: "3.9"

services:
  # === 基础设施 ===
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: content_harvester
      POSTGRES_USER: harvester
      POSTGRES_PASSWORD: ${DB_PASSWORD:-harvester123}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_db.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U harvester"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  # === 网关 ===
  gateway:
    image: nginx:1.25-alpine
    ports:
      - "80:80"
    volumes:
      - ./gateway/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      web-app:
        condition: service_healthy

  # === 业务服务 ===
  web-app:
    build:
      context: ./services/web-app
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://harvester:${DB_PASSWORD:-harvester123}@postgres:5432/content_harvester
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  crawler:
    build:
      context: ./services/crawler
      dockerfile: Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql+asyncpg://harvester:${DB_PASSWORD:-harvester123}@postgres:5432/content_harvester
      - REDIS_URL=redis://redis:6379/0
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
    volumes:
      - ./config:/app/config:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 1G

  media-worker:
    build:
      context: ./services/media-worker
      dockerfile: Dockerfile
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=postgresql+asyncpg://harvester:${DB_PASSWORD:-harvester123}@postgres:5432/content_harvester
      - REDIS_URL=redis://redis:6379/0
      - MODEL_PATH=/models
      - FILE_STORAGE_PATH=/data/files
    volumes:
      - file_storage:/data/files
      - model_data:/models
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      resources:
        limits:
          memory: 4G
    profiles:
      - full                    # 只在 full profile 时启动

  scheduler:
    build:
      context: ./services/scheduler
      dockerfile: Dockerfile
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=postgresql+asyncpg://harvester:${DB_PASSWORD:-harvester123}@postgres:5432/content_harvester
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  # === 前端 ===
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"

volumes:
  postgres_data:
  file_storage:
  model_data:
```

### 15.2 启动命令

```bash
# 日常开发（不启动 Media Worker，省内存）
docker compose up postgres redis web-app frontend scheduler

# 需要转录时
docker compose --profile full up

# 全部启动
docker compose --profile full up

# 只重启某个服务
docker compose restart crawler
```

### 15.3 Nginx 网关配置

```nginx
# gateway/nginx.conf
events { worker_connections 1024; }

http {
    upstream web_app { server web-app:8000; }
    
    server {
        listen 80;
        
        # API 请求 → Web App
        location /api/ {
            proxy_pass http://web_app;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # WebSocket → Web App
        location /ws/ {
            proxy_pass http://web_app;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
        
        # 前端静态文件
        location / {
            proxy_pass http://frontend:80;
        }
    }
}
```

---

## 十六、前端设计

### 16.1 页面结构

```
┌─────────────────────────────────────────────────────────┐
│  Navbar: Logo | 搜索框 | 🔔通知                          │
├─────────────────────────────────────────────────────────┤
│  Sidebar           │  Main Content                      │
│  ┌───────────────┐ │                                    │
│  │ 📊 仪表盘     │ │  (根据左侧选择展示不同内容)         │
│  │ 📄 内容列表   │ │                                    │
│  │ ⏰ 定时任务   │ │                                    │
│  │ ⚙️ 设置      │ │                                    │
│  └───────────────┘ │                                    │
└─────────────────────────────────────────────────────────┘
```

### 16.2 核心页面

| 页面 | 路由 | 功能 |
|------|------|------|
| 仪表盘 | `/` | 搜索入口 + 最近采集 + 统计概览 |
| 内容列表 | `/contents` | 筛选/排序/批量操作 |
| 内容详情 | `/contents/:id` | 预览 + 转录编辑器 + 导出 |
| 定时任务 | `/tasks` | 任务 CRUD + 执行历史 |
| 设置 | `/settings` | 热度权重 + 通知配置 |

### 16.3 组件设计

```
components/
├── layout/
│   ├── AppNavbar.vue           # 顶部导航
│   ├── AppSidebar.vue          # 侧边栏
│   └── AppLayout.vue           # 布局容器
├── content/
│   ├── ContentCard.vue         # 内容卡片
│   ├── ContentFilters.vue      # 筛选器
│   ├── ContentTable.vue        # 表格视图
│   └── PlatformBadge.vue       # 平台标识
├── search/
│   ├── SearchBar.vue           # 搜索输入框
│   └── SearchResults.vue       # 搜索结果列表
├── transcript/
│   ├── TranscriptViewer.vue    # 转录文本查看
│   ├── TranscriptEditor.vue    # 转录文本编辑器（Tiptap）
│   └── TimestampMarker.vue     # 时间戳标记
├── task/
│   ├── TaskForm.vue            # 任务创建/编辑表单
│   ├── CronPicker.vue          # Cron 表达式选择器
│   └── ExecutionHistory.vue    # 执行历史
├── common/
│   ├── ExportDialog.vue        # 导出对话框
│   ├── NotificationBell.vue    # 通知铃铛
│   ├── LoadingState.vue        # 加载状态
│   └── EmptyState.vue          # 空状态
```

### 16.4 状态管理（Pinia）

```typescript
// stores/content.ts
export const useContentStore = defineStore('content', {
  state: () => ({
    contents: [] as Content[],
    currentContent: null as Content | null,
    filters: { platform: null, status: null, keyword: '' },
    pagination: { page: 1, pageSize: 20, total: 0 },
    isLoading: false
  }),
  actions: {
    async fetchContents() { ... },
    async crawlByUrl(url: string) { ... },
    async searchByKeyword(keyword: string, platforms: string[]) { ... },
    async exportContent(id: string, format: string) { ... },
    async updateTranscript(id: string, text: string) { ... }
  }
})

// stores/notification.ts
export const useNotificationStore = defineStore('notification', {
  state: () => ({
    notifications: [] as Notification[],
    unreadCount: 0,
    wsConnection: null as WebSocket | null
  }),
  actions: {
    connectWebSocket() { ... },
    markAsRead(id: string) { ... },
    markAllAsRead() { ... }
  }
})
```

---

## 十七、测试策略

### 17.1 测试金字塔

```
        ╱╲
       ╱ E2E ╲           少量：核心流程端到端
      ╱────────╲
     ╱ 集成测试  ╲        中等：API + DB + 消息队列
    ╱──────────────╲
   ╱    单元测试     ╲     大量：领域逻辑 + 算法
  ╱────────────────────╲
```

### 17.2 各层测试范围

| 层 | 测什么 | 怎么测 |
|----|--------|--------|
| Domain | 热度算法、降级策略、去重逻辑 | 纯单元测试，无 mock |
| Application | 用例编排逻辑 | Mock Port 接口 |
| Infrastructure | 爬虫解析、DB 读写、消息队列 | 用 testcontainers 真实环境 |
| API | 接口参数校验、响应格式 | FastAPI TestClient |

### 17.3 关键测试用例

```python
# 单元测试示例

class TestHotScoreCalculator:
    def test_should_weight_likes_highest(self): ...
    def test_should_decay_old_content(self): ...
    def test_should_handle_zero_metrics(self): ...
    def test_should_use_platform_specific_weights(self): ...

class TestEngineFallbackStrategy:
    def test_should_fallback_on_403(self): ...
    def test_should_fallback_on_captcha(self): ...
    def test_should_not_fallback_on_success(self): ...
    def test_should_start_at_platform_level(self): ...

class TestDeduplicationStrategy:
    def test_should_detect_duplicate_within_window(self): ...
    def test_should_allow_after_window_expires(self): ...

class TestPlatformDetector:
    def test_should_detect_wechat_article(self): ...
    def test_should_detect_douyin_video(self): ...
    def test_should_raise_on_unknown_url(self): ...
```

---

## 十八、安全设计

### 18.1 安全措施

| 风险 | 防护 |
|------|------|
| API Key 泄露 | 环境变量存储，.env 不入 git，日志脱敏 |
| Cookie 泄露 | 数据库加密存储，日志不打印 Cookie 值 |
| 文件路径穿越 | 导出文件名做安全校验，限制下载目录 |
| 大文件攻击 | 限制视频大小（默认 500MB） |
| 消息伪造 | 服务间内网通信，不暴露 Worker 端口 |

### 18.2 速率限制

```python
# API 层速率限制
RATE_LIMITS = {
    "/api/v1/crawl/url": "10/minute",      # 单 URL 采集
    "/api/v1/crawl/search": "5/minute",     # 搜索
    "/api/v1/crawl/batch": "2/minute",      # 批量
    "/api/v1/contents/*/export": "20/minute" # 导出
}
```

---

## 附录 A：技术决策记录（ADR）

| ADR | 决策 | 理由 |
|-----|------|------|
| ADR-001 | 4 个微服务（非 6 个） | 8GB 内存限制 + 个人项目不需过度拆分 |
| ADR-002 | Redis Streams（非 RabbitMQ） | 已有 Redis、内存紧张、功能够用 |
| ADR-003 | SenseVoice（非 Whisper） | 中文效果更好、速度快 15 倍、内存友好 |
| ADR-004 | 三级引擎降级（非固定引擎） | 平衡成本和成功率 |
| ADR-005 | PostgreSQL Schema 隔离（非独立数据库） | 简化运维、M2 资源有限 |
| ADR-006 | FastAPI（非 Django） | 异步性能更好，适合 I/O 密集场景 |
| ADR-007 | Vue 3 + Naive UI（非 React） | 中文社区活跃，个人项目开发效率高 |
| ADR-008 | Docker Compose（非 K8s） | 个人项目不需要集群编排 |

---

## 附录 B：文件清单

本技术设计涉及的全部新建文件约 80+ 个，分布在 4 个服务 + 1 个前端 + 共享库中。开发时按 Phase 逐步创建。

