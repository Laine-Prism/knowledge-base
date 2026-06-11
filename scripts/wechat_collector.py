#!/usr/bin/env python3
"""
微信知识库采集器
- 监控微信本地文件目录，检测新的文件分享
- 监控 URL 收集箱，下载链接内容
- 生成摘要并归档到知识库
"""

import os
import sys
import json
import time
import hashlib
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# === 配置 ===
HOME = Path.home()
WECHAT_BASE = HOME / "Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
WECHAT_USER = "wxid_g6hajc0yk8ea22_3fb2"
WECHAT_FILES = WECHAT_BASE / WECHAT_USER / "msg/file"

PROJECT_ROOT = HOME / "Documents/内容知识库搭建"
KB_ROOT = PROJECT_ROOT / "knowledge_base"
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
STATE_FILE = PROJECT_ROOT / "config/collector_state.json"
URL_INBOX = PROJECT_ROOT / "config/url_inbox.txt"

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".md", ".pdf", ".docx", ".txt", ".html", ".htm"}

# === 状态管理 ===
def load_state():
    """加载采集器状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"seen_files": [], "seen_urls": [], "last_scan": None}

def save_state(state):
    """保存采集器状态"""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_scan"] = datetime.now().isoformat()
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

# === 文件监控 ===
def scan_wechat_files(state):
    """扫描微信文件目录，发现新文件"""
    new_files = []
    if not WECHAT_FILES.exists():
        print(f"[警告] 微信文件目录不存在: {WECHAT_FILES}")
        return new_files

    for fpath in WECHAT_FILES.rglob("*"):
        if not fpath.is_file():
            continue
        if fpath.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        
        file_hash = hashlib.md5(str(fpath).encode()).hexdigest()
        if file_hash not in state.get("seen_files", []):
            new_files.append(fpath)
            state.setdefault("seen_files", []).append(file_hash)
    
    return new_files

def collect_file(filepath):
    """将微信分享的文件收录到知识库"""
    # 确定目标路径
    today = datetime.now().strftime("%Y-%m-%d")
    dest_dir = DOWNLOADS_DIR / today
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    dest_path = dest_dir / filepath.name
    # 避免重名
    if dest_path.exists():
        stem = filepath.stem
        suffix = filepath.suffix
        dest_path = dest_dir / f"{stem}_{int(time.time())}{suffix}"
    
    shutil.copy2(filepath, dest_path)
    print(f"[收录文件] {filepath.name} -> {dest_path}")
    return dest_path

# === URL 采集 ===
def scan_url_inbox(state):
    """扫描 URL 收集箱中的新链接"""
    new_urls = []
    if not URL_INBOX.exists():
        # 创建空文件
        URL_INBOX.parent.mkdir(parents=True, exist_ok=True)
        URL_INBOX.write_text("# 在此粘贴要采集的链接，每行一个\n# 以 # 开头的行会被忽略\n\n")
        return new_urls

    with open(URL_INBOX, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("http"):
                if line not in state.get("seen_urls", []):
                    new_urls.append(line)
                    state.setdefault("seen_urls", []).append(line)
    
    return new_urls

def download_url(url):
    """下载链接内容并保存"""
    today = datetime.now().strftime("%Y-%m-%d")
    dest_dir = DOWNLOADS_DIR / today
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 根据 URL 类型选择下载方式
    if "mp.weixin.qq.com" in url:
        return download_wechat_article(url, dest_dir)
    else:
        return download_generic_page(url, dest_dir)

def download_wechat_article(url, dest_dir):
    """下载微信公众号文章"""
    try:
        import urllib.request
        import re
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        # 提取标题
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.DOTALL)
        if not title_match:
            title_match = re.search(r'<title>(.*?)</title>', html)
        title = title_match.group(1).strip() if title_match else "untitled"
        title = re.sub(r'<[^>]+>', '', title)  # 去除 HTML 标签
        title = re.sub(r'[\\/:*?"<>|]', '_', title)  # 文件名安全化
        
        # 提取正文
        content_match = re.search(
            r'id="js_content"[^>]*>(.*?)</div>\s*<!--', html, re.DOTALL
        )
        if content_match:
            content = content_match.group(1)
        else:
            content = html
        
        # 简单去除 HTML 标签，保留文本
        text = re.sub(r'<br\s*/?>', '\n', content)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        
        # 保存
        filename = f"{title[:80]}.md"
        filepath = dest_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"> 来源: {url}\n")
            f.write(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("---\n\n")
            f.write(text)
        
        print(f"[下载成功] 微信文章: {title}")
        return filepath
    except Exception as e:
        print(f"[下载失败] {url}: {e}")
        return None

def download_generic_page(url, dest_dir):
    """下载通用网页"""
    try:
        import urllib.request
        import re
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        
        # 提取标题
        title_match = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
        title = title_match.group(1).strip() if title_match else "untitled"
        title = re.sub(r'[\\/:*?"<>|]', '_', title)
        
        # 提取正文（简化版）
        # 去除 script 和 style
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'<p[^>]*>', '\n', text)
        text = re.sub(r'</p>', '\n', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text).strip()
        
        # 保存
        filename = f"{title[:80]}.md"
        filepath = dest_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(f"> 来源: {url}\n")
            f.write(f"> 采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("---\n\n")
            f.write(text)
        
        print(f"[下载成功] 网页: {title}")
        return filepath
    except Exception as e:
        print(f"[下载失败] {url}: {e}")
        return None

# === 主循环 ===
def run_once():
    """执行一次扫描"""
    state = load_state()
    results = {"new_files": [], "new_urls": [], "downloaded": []}
    
    # 1. 扫描微信文件目录
    print("\n[扫描] 检查微信文件分享...")
    new_files = scan_wechat_files(state)
    for fpath in new_files:
        collected = collect_file(fpath)
        if collected:
            results["new_files"].append(str(collected))
    
    # 2. 扫描 URL 收集箱
    print("[扫描] 检查 URL 收集箱...")
    new_urls = scan_url_inbox(state)
    for url in new_urls:
        downloaded = download_url(url)
        if downloaded:
            results["downloaded"].append(str(downloaded))
            results["new_urls"].append(url)
    
    # 保存状态
    save_state(state)
    
    # 汇报结果
    total = len(results["new_files"]) + len(results["downloaded"])
    if total > 0:
        print(f"\n[完成] 本次采集: {len(results['new_files'])} 个文件, {len(results['downloaded'])} 个链接")
    else:
        print("[完成] 未发现新内容")
    
    return results

def run_daemon(interval=60):
    """守护进程模式，持续监控"""
    print(f"=== 微信知识库采集器启动 ===")
    print(f"监控目录: {WECHAT_FILES}")
    print(f"URL 收集箱: {URL_INBOX}")
    print(f"扫描间隔: {interval}秒")
    print(f"下载目录: {DOWNLOADS_DIR}")
    print("=" * 40)
    
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            print("\n[停止] 采集器已停止")
            break
        except Exception as e:
            print(f"[错误] {e}")
        
        time.sleep(interval)

# === 入口 ===
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        run_daemon(interval)
    else:
        run_once()
