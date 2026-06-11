---
title: ContentHarvester — 架构分层设计（架构师方案）
date: 2026-06-11
source: 微信群文件分享
category: 技术/架构设计
summary_method: manual
---

## 📝 摘要

本文为 ContentHarvester 项目设计了基于整洁架构与六边形思想的四层分层架构，核心目标是防止代码腐化、实现可维护和可扩展。文章首先对比了MVC、三层架构、整洁架构、六边形架构、DDD等主流模式，认为六边形架构最适合该项目——因为项目外部依赖多且会变（爬虫接口、ASR引擎），但核心业务流程稳定。

四层设计为：接口层（FastAPI路由，只做请求响应）→ 应用层（用例编排，协调业务流程）→ 领域层（纯业务逻辑，零外部依赖）← 基础设施层（具体实现如爬虫、数据库、ASR）。依赖方向严格从外向内，通过Port接口定义契约，Adapter提供具体实现，依赖注入容器完成组装。

文章制定了8条防屎山规则，包括领域层零依赖、单文件不超200行、接口先行、不允许跨层调用等。这套架构的实际价值在于：抖音接口挂了只改一个adapter文件、换ASR引擎只改配置、新增平台只需实现接口——核心业务逻辑永远不需要改动。

---

## 📄 原文

# ContentHarvester — 架构分层设计（架构师方案）

> 核心目标：防屎山，可维护，可扩展，每一层职责清晰

---

## 一、主流架构模式对比

| 架构模式 | 适用场景 | 复杂度 | 我们是否适合 |
|---------|---------|--------|------------|
| **MVC** (Model-View-Controller) | 简单 Web 应用 | ⭐ | ❌ 太简单，业务一复杂就乱 |
| **三层架构** (Controller-Service-DAO) | 传统企业应用 | ⭐⭐ | ⚠️ 能用但不够 |
| **整洁架构** (Clean Architecture) | 中大型项目 | ⭐⭐⭐ | ✅ 适合 |
| **六边形架构** (Hexagonal/Ports & Adapters) | 需要对接多外部系统 | ⭐⭐⭐ | ✅ 非常适合！ |
| **DDD** (领域驱动设计) | 复杂业务领域 | ⭐⭐⭐⭐ | ⚠️ 过度设计 |
| **微服务** | 大团队/大系统 | ⭐⭐⭐⭐⭐ | ❌ 个人项目不需要 |

---

## 二、推荐方案：整洁架构 + 六边形思想

### 为什么选这个？

你的项目特点：
1. **外部依赖多且会变** — 抖音接口会变、公众号反爬会升级、ASR 引擎可能换
2. **核心逻辑稳定** — "搜索→抓取→转录→导出" 这个流程不会变
3. **需要可替换** — 三级浏览器引擎要能切换，ASR 要能换

**六边形架构的核心思想：把"会变的"和"不变的"隔离开。**

```
外面的世界（会变的）        你的核心业务（不变的）        外面的世界（会变的）
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│ Web UI      │         │              │         │ 抖音 API    │
│ API 接口    │────→    │   核心逻辑    │    ←────│ 公众号页面  │
│ 定时任务    │  Port   │   (纯业务)    │  Port   │ DeepSeek    │
│             │         │              │         │ SenseVoice  │
└─────────────┘         └──────────────┘         └─────────────┘
  (驱动端适配器)              (领域层)              (被驱动端适配器)
```

**好处：核心业务代码永远不需要改，只需要换"适配器"。**

比如：抖音接口挂了 → 只改 `adapters/douyin.py`，核心逻辑一行不动。

---

## 三、四层架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  第 1 层：接口层 (Interface / API Layer)                     │
│  ├─ HTTP API 路由（FastAPI Router）                          │
│  ├─ 请求参数校验（Pydantic Schema）                          │
│  ├─ 响应格式化                                               │
│  └─ 职责：只负责"接收请求，返回响应"，不含业务逻辑            │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第 2 层：应用层 (Application / Use Case Layer)              │
│  ├─ 用例编排（Use Cases）                                    │
│  ├─ 业务流程协调                                             │
│  └─ 职责：编排"做什么"，不关心"怎么做"                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第 3 层：领域层 (Domain Layer)                               │
│  ├─ 实体模型（Content, Task, Notification）                  │
│  ├─ 业务规则（热度排序算法、降级策略）                         │
│  ├─ 接口定义（Port / Protocol）                              │
│  └─ 职责：纯业务逻辑，零外部依赖                              │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  第 4 层：基础设施层 (Infrastructure / Adapter Layer)         │
│  ├─ 数据库实现（PostgreSQL Repository）                      │
│  ├─ 爬虫实现（DrissionPage / Playwright / browser-use）      │
│  ├─ ASR 实现（SenseVoice）                                   │
│  ├─ 视频下载实现（yt-dlp / Douyin API）                      │
│  ├─ 通知实现（站内 / 微信 / 飞书）                            │
│  └─ 职责：具体技术实现，可随时替换                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 四、依赖规则（防屎山的核心铁律）

```
    接口层 → 应用层 → 领域层 ← 基础设施层
    
    箭头方向 = 依赖方向 = import 方向
```

**铁律：**
1. **内层绝不依赖外层** — 领域层不能 import FastAPI、不能 import SQLAlchemy
2. **外层依赖内层** — 基础设施层实现领域层定义的接口
3. **依赖倒置** — 领域层定义"接口"(Protocol)，基础设施层提供"实现"

**举例：**
```python
# ❌ 屎山写法：核心逻辑直接依赖具体实现
class CrawlService:
    def crawl(self, url):
        from drissionpage import ChromiumPage  # 核心层直接依赖外部库！
        page = ChromiumPage()
        ...

# ✅ 整洁写法：核心逻辑只依赖抽象接口
class CrawlService:
    def __init__(self, browser: BrowserPort):  # 依赖抽象
        self.browser = browser
    
    def crawl(self, url):
        return self.browser.fetch(url)  # 不关心具体用什么引擎
```

---

## 五、具体目录结构

```
content-harvester/
├── docker-compose.yml
├── .env.example
│
├── backend/
│   ├── app/
│   │   │
│   │   ├── api/                          ← 第 1 层：接口层
│   │   │   ├── __init__.py
│   │   │   ├── deps.py                   # 依赖注入
│   │   │   ├── v1/
│   │   │   │   ├── crawl.py             # 采集相关路由
│   │   │   │   ├── contents.py          # 内容管理路由
│   │   │   │   ├── tasks.py             # 定时任务路由
│   │   │   │   └── notifications.py     # 通知路由
│   │   │   └── schemas/                  # 请求/响应模型
│   │   │       ├── crawl.py
│   │   │       ├── content.py
│   │   │       └── task.py
│   │   │
│   │   ├── application/                  ← 第 2 层：应用层（用例）
│   │   │   ├── __init__.py
│   │   │   ├── crawl_article.py          # 用例：采集文章
│   │   │   ├── download_video.py         # 用例：下载视频
│   │   │   ├── transcribe_video.py       # 用例：转录视频
│   │   │   ├── search_content.py         # 用例：搜索热门内容
│   │   │   ├── export_content.py         # 用例：导出内容
│   │   │   └── schedule_task.py          # 用例：管理定时任务
│   │   │
│   │   ├── domain/                       ← 第 3 层：领域层（核心）
│   │   │   ├── __init__.py
│   │   │   ├── entities/                 # 实体
│   │   │   │   ├── content.py            # Content 实体
│   │   │   │   ├── task.py               # ScheduledTask 实体
│   │   │   │   └── notification.py       # Notification 实体
│   │   │   ├── value_objects/            # 值对象
│   │   │   │   ├── platform.py           # Platform 枚举
│   │   │   │   ├── hot_score.py          # 热度评分
│   │   │   │   └── transcript.py         # 转录结果
│   │   │   ├── services/                 # 领域服务（纯业务规则）
│   │   │   │   ├── scoring.py            # 热度排序算法
│   │   │   │   └── fallback.py           # 引擎降级策略
│   │   │   └── ports/                    # 端口定义（接口契约）
│   │   │       ├── browser_port.py       # 浏览器引擎接口
│   │   │       ├── crawler_port.py       # 爬虫接口
│   │   │       ├── downloader_port.py    # 下载器接口
│   │   │       ├── transcriber_port.py   # ASR 接口
│   │   │       ├── repository_port.py    # 数据存储接口
│   │   │       ├── notifier_port.py      # 通知接口
│   │   │       └── exporter_port.py      # 导出接口
│   │   │
│   │   ├── infrastructure/               ← 第 4 层：基础设施层（实现）
│   │   │   ├── __init__.py
│   │   │   ├── browser/                  # 浏览器引擎实现
│   │   │   │   ├── drission_adapter.py   # L1: DrissionPage
│   │   │   │   ├── playwright_adapter.py # L2: Playwright
│   │   │   │   ├── browseruse_adapter.py # L3: browser-use
│   │   │   │   └── smart_browser.py      # 智能降级适配器
│   │   │   ├── crawlers/                 # 各平台爬虫实现
│   │   │   │   ├── wechat_crawler.py
│   │   │   │   ├── toutiao_crawler.py
│   │   │   │   ├── douyin_crawler.py
│   │   │   │   └── wechat_video_crawler.py
│   │   │   ├── downloaders/              # 视频下载实现
│   │   │   │   ├── douyin_downloader.py
│   │   │   │   ├── wechat_video_downloader.py
│   │   │   │   └── ytdlp_downloader.py
│   │   │   ├── transcribers/             # ASR 实现
│   │   │   │   ├── sensevoice_adapter.py
│   │   │   │   └── whisper_adapter.py    # 备选
│   │   │   ├── persistence/              # 数据库实现
│   │   │   │   ├── database.py           # 连接管理
│   │   │   │   ├── models.py             # ORM 模型
│   │   │   │   └── repositories/
│   │   │   │       ├── content_repo.py
│   │   │   │       ├── task_repo.py
│   │   │   │       └── notification_repo.py
│   │   │   ├── notifiers/                # 通知实现
│   │   │   │   ├── in_app_notifier.py
│   │   │   │   ├── wechat_notifier.py    # 后续
│   │   │   │   └── feishu_notifier.py    # 后续
│   │   │   ├── exporters/                # 导出实现
│   │   │   │   ├── markdown_exporter.py
│   │   │   │   ├── word_exporter.py
│   │   │   │   └── pdf_exporter.py
│   │   │   └── tasks/                    # Celery 异步任务
│   │   │       ├── celery_app.py
│   │   │       ├── crawl_tasks.py
│   │   │       └── transcribe_tasks.py
│   │   │
│   │   ├── main.py                       # FastAPI 入口
│   │   ├── config.py                     # 配置管理
│   │   └── container.py                  # 依赖注入容器
│   │
│   ├── alembic/                          # 数据库迁移
│   ├── tests/
│   │   ├── unit/                         # 单元测试（测领域层）
│   │   ├── integration/                  # 集成测试（测基础设施层）
│   │   └── e2e/                          # 端到端测试
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                             # 前端（独立关注）
│   ├── src/
│   │   ├── views/
│   │   ├── components/
│   │   ├── composables/                  # Vue 3 组合式函数
│   │   ├── api/
│   │   ├── stores/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
│
└── config/
    ├── browser_engines.yaml
    ├── platforms.yaml
    └── notifications.yaml
```

---

## 六、关键代码示例（展示各层如何协作）

### 第 3 层：领域层 — 定义接口（Port）

```python
# domain/ports/crawler_port.py
from abc import ABC, abstractmethod
from domain.entities.content import Content

class CrawlerPort(ABC):
    """爬虫接口契约 — 所有平台爬虫必须实现这个"""
    
    @abstractmethod
    async def fetch_article(self, url: str) -> Content:
        """抓取文章，返回统一的 Content 实体"""
        pass
    
    @abstractmethod
    async def search(self, keyword: str, limit: int = 20) -> list[Content]:
        """搜索内容"""
        pass
```

```python
# domain/ports/transcriber_port.py
from abc import ABC, abstractmethod
from domain.value_objects.transcript import TranscriptResult

class TranscriberPort(ABC):
    """ASR 接口契约 — 不管用 SenseVoice 还是 Whisper"""
    
    @abstractmethod
    async def transcribe(self, audio_path: str) -> TranscriptResult:
        pass
```

### 第 4 层：基础设施层 — 实现接口

```python
# infrastructure/crawlers/wechat_crawler.py
from domain.ports.crawler_port import CrawlerPort
from domain.entities.content import Content

class WechatArticleCrawler(CrawlerPort):
    """微信公众号爬虫 — 实现 CrawlerPort 接口"""
    
    def __init__(self, browser: SmartBrowser):
        self.browser = browser
    
    async def fetch_article(self, url: str) -> Content:
        # 具体实现：用 DrissionPage/Playwright 抓取
        html = await self.browser.fetch(url, platform="wechat")
        return Content(
            title=self._extract_title(html),
            body=self._extract_body(html),
            platform="wechat",
            ...
        )
```

### 第 2 层：应用层 — 编排用例

```python
# application/crawl_article.py
from domain.ports.crawler_port import CrawlerPort
from domain.ports.repository_port import ContentRepository

class CrawlArticleUseCase:
    """用例：采集一篇文章"""
    
    def __init__(self, crawler: CrawlerPort, repo: ContentRepository):
        self.crawler = crawler      # 不知道具体是哪个爬虫
        self.repo = repo            # 不知道具体是什么数据库
    
    async def execute(self, url: str) -> Content:
        # 1. 抓取
        content = await self.crawler.fetch_article(url)
        # 2. 保存
        await self.repo.save(content)
        # 3. 返回
        return content
```

### 第 1 层：接口层 — 处理 HTTP

```python
# api/v1/crawl.py
from fastapi import APIRouter, Depends
from api.deps import get_crawl_use_case
from api.schemas.crawl import CrawlRequest, CrawlResponse

router = APIRouter()

@router.post("/crawl/url")
async def crawl_by_url(
    request: CrawlRequest,
    use_case = Depends(get_crawl_use_case)  # 依赖注入
):
    content = await use_case.execute(request.url)
    return CrawlResponse.from_entity(content)
```

### 依赖注入容器 — 把各层组装起来

```python
# container.py
from infrastructure.browser.smart_browser import SmartBrowser
from infrastructure.crawlers.wechat_crawler import WechatArticleCrawler
from infrastructure.crawlers.toutiao_crawler import ToutiaoCrawler
from infrastructure.persistence.repositories.content_repo import PostgresContentRepo
from application.crawl_article import CrawlArticleUseCase

class Container:
    """依赖注入容器 — 在这里决定用哪个具体实现"""
    
    def __init__(self, config):
        # 基础设施
        self.browser = SmartBrowser(config.browser)
        self.content_repo = PostgresContentRepo(config.database)
        
        # 爬虫（可以随时换实现）
        self.crawlers = {
            "wechat": WechatArticleCrawler(self.browser),
            "toutiao": ToutiaoCrawler(self.browser),
        }
    
    def get_crawl_use_case(self, platform: str) -> CrawlArticleUseCase:
        return CrawlArticleUseCase(
            crawler=self.crawlers[platform],
            repo=self.content_repo
        )
```

---

## 七、防屎山规则清单

| # | 规则 | 怎么检查 |
|---|------|---------|
| 1 | **领域层零依赖** | `domain/` 下的文件不能 import fastapi、sqlalchemy、playwright 等 |
| 2 | **一个文件一个职责** | 每个文件不超过 200 行 |
| 3 | **接口先行** | 先写 Port（接口），再写 Adapter（实现） |
| 4 | **用例单一** | 每个 Use Case 只做一件事 |
| 5 | **不允许跨层调用** | API 层不能直接调基础设施层 |
| 6 | **配置外置** | 所有可变配置放 yaml/env，不硬编码 |
| 7 | **命名统一** | Port 结尾用 `_port`，Adapter 结尾用 `_adapter` |
| 8 | **测试跟随** | 每个 Use Case 必须有对应的单元测试 |

---

## 八、这套架构解决了什么问题？

| 问题 | 屎山写法 | 整洁架构写法 |
|------|---------|------------|
| 抖音接口挂了 | 到处改代码，牵一发动全身 | 只改 `infrastructure/crawlers/douyin_crawler.py` |
| 想换 ASR 引擎 | 全局搜索替换，漏一个就报错 | 新写一个 adapter，改一行注入配置 |
| 加一个新平台 | 复制粘贴大量重复代码 | 实现 CrawlerPort 接口，注册到容器 |
| 想加飞书通知 | 在业务代码里到处加 if-else | 新写 FeishuNotifier，配置文件开启 |
| 写单元测试 | 没法测，因为到处耦合数据库和网络 | 领域层纯逻辑，mock 接口即可测试 |

---

## 九、确认问题

请你确认以下几点：

1. **四层架构**（接口层 → 应用层 → 领域层 ← 基础设施层）你认可吗？
2. **依赖注入**的方式你能接受吗？（代码稍微多一点，但换来可维护性）
3. **目录结构**你觉得清晰吗？有想调整的吗？
4. **防屎山规则**有没有你想加的？

