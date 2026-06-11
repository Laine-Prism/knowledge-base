# 📚 AI 知识库采集系统

自动从微信群聊中采集分享的文件和链接，生成摘要后归档到本地知识库。

## 系统架构

```
微信群聊 ──→ 本地文件监控 ──→ 采集器 ──→ 下载 ──→ 摘要生成 ──→ 知识库归档
                                  ↑
URL 收集箱（手动/半自动）────────┘
```

## 目录结构

```
内容知识库搭建/
├── README.md
├── config/
│   ├── settings.yaml        # 配置文件
│   ├── url_inbox.txt        # URL 收集箱（粘贴链接到此文件）
│   └── collector_state.json # 采集状态（自动维护）
├── scripts/
│   ├── wechat_collector.py  # 微信文件监控 + URL 下载
│   ├── summarizer.py        # 摘要生成 + 知识库归档
│   ├── run_pipeline.py      # 一键运行完整流水线
│   └── add_url.py           # 快速添加 URL 到收集箱
├── downloads/               # 下载的原始文件（按日期）
│   └── 2026-06-11/
└── knowledge_base/          # 知识库（按分类）
    ├── 技术/AI与大模型/
    ├── 技术/架构设计/
    ├── 技术/编程开发/
    ├── 技术/DevOps/
    ├── 产品/设计/
    ├── 商业/创业/
    ├── 认知/思维/
    └── 未分类/
```

## 快速开始

### 1. 一键运行（推荐）

```bash
cd ~/Documents/内容知识库搭建
python3 scripts/run_pipeline.py
```

这会自动：
- 扫描微信新分享的文件
- 下载 URL 收集箱中的链接
- 生成摘要
- 归档到知识库

### 2. 添加要采集的链接

方式 A：直接编辑 URL 收集箱
```bash
open config/url_inbox.txt
# 每行粘贴一个链接
```

方式 B：命令行添加
```bash
python3 scripts/add_url.py https://mp.weixin.qq.com/s/xxxxx
```

方式 C：从剪贴板添加（复制链接后运行）
```bash
python3 scripts/add_url.py
```

### 3. 后台持续监控

```bash
python3 scripts/wechat_collector.py --daemon 60
# 每 60 秒扫描一次
```

### 4. 单独处理某个文件

```bash
python3 scripts/summarizer.py path/to/article.md
```

## 摘要生成

摘要生成支持三种方式（按优先级自动选择）：

1. **OpenAI API**（最佳质量）— 需设置环境变量：
   ```bash
   export OPENAI_API_KEY="sk-..."
   ```

2. **Ollama 本地模型** — 需安装并运行 Ollama：
   ```bash
   ollama run qwen2.5:7b
   ```

3. **提取式摘要**（兜底）— 自动提取关键段落，无需外部依赖

## 知识库条目格式

每篇归档的内容格式如下：

```markdown
---
title: 文章标题
date: 2026-06-11
source: https://...
category: 技术/AI与大模型
summary_method: openai
---

## 📝 摘要

[300-500字摘要，包含核心主题、关键观点、实用价值]

---

## 📄 原文

[完整原文内容]
```

## 工作原理

### 微信文件采集
微信 macOS 客户端会将群聊中分享的文件保存到本地目录：
```
~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/
```
脚本通过监控此目录的变化来检测新文件，无需破解数据库加密。

### URL 链接采集
由于微信消息数据库已加密，消息中的链接无法直接读取。
当前方案是通过 **URL 收集箱** 半自动收集：
- 看到群里有人分享链接时，复制后运行 `add_url.py`
- 或直接粘贴到 `url_inbox.txt`

> 后续可对接飞书 Bot API 实现全自动链接采集

## 后续扩展

- [ ] 飞书群 Bot 自动采集链接
- [ ] macOS 快捷指令 + 通知中心集成
- [ ] 全文搜索功能
- [ ] Web 界面浏览知识库
- [ ] 标签系统和交叉引用
