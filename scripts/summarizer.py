#!/usr/bin/env python3
"""
摘要生成器
读取下载的文件内容，生成 300-500 字的摘要，并输出为知识库格式。
支持多种方式：
1. OpenAI API（需要设置 OPENAI_API_KEY）
2. 本地 Ollama
3. 简单的提取式摘要（无需 AI，作为兜底）
"""

import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path.home() / "Documents/内容知识库搭建"
KB_ROOT = PROJECT_ROOT / "knowledge_base"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx", ".txt", ".html", ".htm"}

# === 文件读取 ===
def read_content(filepath):
    """读取文件内容"""
    filepath = Path(filepath)
    
    if filepath.suffix == ".md":
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    elif filepath.suffix == ".txt":
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    elif filepath.suffix == ".pdf":
        return extract_pdf_text(filepath)
    elif filepath.suffix == ".html" or filepath.suffix == ".htm":
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()
        return html_to_text(html)
    else:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def extract_pdf_text(filepath):
    """提取 PDF 文本（需要 PyPDF2 或 pdfplumber）"""
    try:
        import subprocess
        # 尝试用系统自带的 textutil
        result = subprocess.run(
            ["mdimport", "-d2", str(filepath)],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout:
            return result.stdout
    except Exception:
        pass
    
    # 兜底：提示用户
    return f"[PDF 文件: {filepath.name}，需要安装 pdfplumber 才能提取文本]"

def html_to_text(html):
    """简单的 HTML 转文本"""
    text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<p[^>]*>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

# === 摘要生成 ===
def generate_summary_openai(content, max_chars=500):
    """使用 OpenAI API 生成摘要"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    
    try:
        import urllib.request
        import json as json_mod
        
        # 截断过长内容
        if len(content) > 8000:
            content = content[:8000] + "\n...[内容已截断]"
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的内容摘要助手。请阅读以下内容，生成一段300-500字的中文摘要。摘要需要：1. 明确文章的核心主题；2. 提炼关键观点（3-5个）；3. 说明实用价值或启发。语言精炼，逻辑清晰。"
                },
                {
                    "role": "user",
                    "content": content
                }
            ],
            "max_tokens": 800,
            "temperature": 0.3
        }
        
        data = json_mod.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json_mod.loads(resp.read().decode("utf-8"))
        
        summary = result["choices"][0]["message"]["content"]
        return summary
    except Exception as e:
        print(f"[OpenAI 摘要失败] {e}")
        return None

def generate_summary_ollama(content, max_chars=500):
    """使用本地 Ollama 生成摘要"""
    try:
        import urllib.request
        import json as json_mod
        
        if len(content) > 6000:
            content = content[:6000] + "\n...[内容已截断]"
        
        payload = {
            "model": "qwen2.5:7b",
            "prompt": f"请阅读以下内容，生成一段300-500字的中文摘要。摘要需要明确核心主题、提炼关键观点、说明实用价值。\n\n内容：\n{content}\n\n摘要：",
            "stream": False
        }
        
        data = json_mod.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json_mod.loads(resp.read().decode("utf-8"))
        
        return result.get("response", "")
    except Exception as e:
        print(f"[Ollama 摘要失败] {e}")
        return None

def generate_summary_extractive(content, max_chars=500):
    """
    提取式摘要（兜底方案，不需要 AI）
    原理：提取关键句子组成摘要
    """
    # 按段落分割
    paragraphs = [p.strip() for p in content.split("\n") if p.strip()]
    
    # 过滤掉太短的行（可能是标题、分隔符等）
    sentences = []
    for p in paragraphs:
        if len(p) > 20 and not p.startswith(("#", ">", "|", "```", "---", "===")):
            sentences.append(p)
    
    if not sentences:
        return content[:max_chars]
    
    # 取前几个有内容的段落
    summary_parts = []
    char_count = 0
    for s in sentences:
        if char_count + len(s) > max_chars:
            # 截断最后一句
            remaining = max_chars - char_count
            if remaining > 50:
                summary_parts.append(s[:remaining] + "...")
            break
        summary_parts.append(s)
        char_count += len(s)
    
    return "\n".join(summary_parts)

def generate_summary(content):
    """
    生成摘要，按优先级尝试不同方式：
    1. OpenAI API
    2. Ollama 本地模型
    3. 提取式摘要
    """
    # 尝试 OpenAI
    summary = generate_summary_openai(content)
    if summary:
        return summary, "openai"
    
    # 尝试 Ollama
    summary = generate_summary_ollama(content)
    if summary:
        return summary, "ollama"
    
    # 兜底：提取式
    summary = generate_summary_extractive(content)
    return summary, "extractive"

# === 知识库归档 ===
def archive_to_knowledge_base(filepath, summary, method):
    """将内容归档到知识库，格式为：摘要 + 原文"""
    filepath = Path(filepath)
    content = read_content(filepath)
    
    # 提取元信息
    title = extract_title(content, filepath)
    source_url = extract_source_url(content)
    
    # 确定分类目录
    category = classify_content(content, title)
    
    # 生成知识库条目
    today = datetime.now().strftime("%Y-%m-%d")
    kb_dir = KB_ROOT / category / today
    kb_dir.mkdir(parents=True, exist_ok=True)
    
    # 文件名
    safe_title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
    kb_file = kb_dir / f"{safe_title}.md"
    
    with open(kb_file, "w", encoding="utf-8") as f:
        # 头部元信息
        f.write(f"---\n")
        f.write(f"title: {title}\n")
        f.write(f"date: {today}\n")
        f.write(f"source: {source_url or '微信群文件分享'}\n")
        f.write(f"category: {category}\n")
        f.write(f"summary_method: {method}\n")
        f.write(f"---\n\n")
        
        # 摘要部分
        f.write(f"## 📝 摘要\n\n")
        f.write(f"{summary}\n\n")
        
        # 分隔线
        f.write(f"---\n\n")
        
        # 原文部分
        f.write(f"## 📄 原文\n\n")
        f.write(content)
    
    print(f"[归档完成] {category}/{safe_title}.md (摘要方式: {method})")
    return kb_file

def extract_title(content, filepath):
    """从内容中提取标题"""
    # 尝试从 Markdown 标题提取
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # 尝试从 YAML front matter 提取
    match = re.search(r'^title:\s*(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    
    # 使用文件名
    return filepath.stem

def extract_source_url(content):
    """从内容中提取来源 URL"""
    match = re.search(r'来源:\s*(https?://\S+)', content)
    if match:
        return match.group(1)
    match = re.search(r'(https?://\S+)', content)
    if match:
        return match.group(1)
    return None

def classify_content(content, title):
    """
    简单的内容分类
    根据关键词将内容归类到不同目录
    """
    text = (title + " " + content[:2000]).lower()
    
    categories = {
        "技术/AI与大模型": ["ai", "gpt", "llm", "大模型", "机器学习", "深度学习", "transformer", "openai", "claude", "prompt"],
        "技术/架构设计": ["微服务", "架构", "设计模式", "分布式", "系统设计", "ddd", "领域驱动"],
        "技术/编程开发": ["python", "javascript", "golang", "rust", "代码", "编程", "开发", "api", "sdk"],
        "技术/DevOps": ["docker", "k8s", "kubernetes", "ci/cd", "部署", "运维", "云原生"],
        "产品/设计": ["产品", "用户体验", "ux", "ui", "设计", "需求", "原型"],
        "商业/创业": ["商业", "创业", "融资", "商业模式", "增长", "营收"],
        "认知/思维": ["认知", "思维", "学习", "方法论", "心智", "决策"],
        "行业/资讯": ["行业", "趋势", "报告", "市场", "分析"],
    }
    
    for category, keywords in categories.items():
        for kw in keywords:
            if kw in text:
                return category
    
    return "未分类"

# === CLI 入口 ===
def process_file(filepath):
    """处理单个文件：读取 -> 生成摘要 -> 归档"""
    filepath = Path(filepath)
    if not filepath.exists():
        print(f"[错误] 文件不存在: {filepath}")
        return None
    
    print(f"\n[处理] {filepath.name}")
    
    # 读取内容
    content = read_content(filepath)
    if not content or len(content) < 50:
        print(f"[跳过] 内容太短: {filepath.name}")
        return None
    
    # 生成摘要
    print(f"[生成摘要]...")
    summary, method = generate_summary(content)
    
    # 归档
    kb_file = archive_to_knowledge_base(filepath, summary, method)
    return kb_file

def process_downloads_dir():
    """处理 downloads 目录中所有未归档的文件"""
    processed_file = PROJECT_ROOT / "config/processed_files.json"
    
    if processed_file.exists():
        with open(processed_file, "r") as f:
            processed = set(json.load(f))
    else:
        processed = set()
    
    new_count = 0
    for fpath in DOWNLOADS_DIR.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        if str(fpath) in processed:
            continue
        
        result = process_file(fpath)
        if result:
            processed.add(str(fpath))
            new_count += 1
    
    # 保存已处理列表
    processed_file.parent.mkdir(parents=True, exist_ok=True)
    with open(processed_file, "w") as f:
        json.dump(list(processed), f, ensure_ascii=False, indent=2)
    
    print(f"\n[完成] 本次处理 {new_count} 个文件")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 处理指定文件
        for fpath in sys.argv[1:]:
            process_file(fpath)
    else:
        # 处理所有未归档的下载
        process_downloads_dir()
