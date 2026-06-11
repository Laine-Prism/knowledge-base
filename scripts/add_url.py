#!/usr/bin/env python3
"""
快捷添加 URL 到收集箱
用法:
  python3 add_url.py https://example.com/article
  python3 add_url.py  (无参数时从剪贴板读取)
"""

import sys
import subprocess
from pathlib import Path

URL_INBOX = Path.home() / "Documents/内容知识库搭建/config/url_inbox.txt"

def get_clipboard():
    """从 macOS 剪贴板获取内容"""
    try:
        result = subprocess.run(["pbpaste"], capture_output=True, text=True)
        return result.stdout.strip()
    except Exception:
        return None

def add_url(url):
    """添加 URL 到收集箱"""
    if not url.startswith("http"):
        print(f"[跳过] 不是有效的 URL: {url}")
        return False
    
    # 检查是否已存在
    if URL_INBOX.exists():
        existing = URL_INBOX.read_text()
        if url in existing:
            print(f"[跳过] URL 已在收集箱中: {url}")
            return False
    
    with open(URL_INBOX, "a", encoding="utf-8") as f:
        f.write(url + "\n")
    
    print(f"[已添加] {url}")
    return True

if __name__ == "__main__":
    if len(sys.argv) > 1:
        for url in sys.argv[1:]:
            add_url(url)
    else:
        # 从剪贴板读取
        clip = get_clipboard()
        if clip and clip.startswith("http"):
            add_url(clip)
        else:
            print("用法: python3 add_url.py <URL>")
            print("  或复制链接后直接运行（自动读取剪贴板）")
