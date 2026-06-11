#!/usr/bin/env python3
"""
知识库本地 HTTP 服务器
提供两个 API：
- GET  /api/structure  → 返回知识库目录树
- GET  /api/search?q=  → 全文搜索
- GET  /api/article?path= → 获取文章内容
"""
import http.server
import json
import re
import os
import urllib.parse
from pathlib import Path

KB_ROOT = Path.home() / "Documents/内容知识库搭建/knowledge_base"
WEB_ROOT = Path.home() / "Documents/内容知识库搭建/web"

def parse_frontmatter(text):
    """解析 YAML front matter"""
    result = {}
    if text.startswith("---"):
        end = text.find("---", 3)
        if end > 0:
            fm = text[3:end]
            for line in fm.strip().split("\n"):
                if ":" in line:
                    key, _, val = line.partition(":")
                    result[key.strip()] = val.strip()
            content = text[end + 3:].strip()
            return result, content
    return result, text

def extract_summary(content):
    """提取摘要部分"""
    match = re.search(r'## 📝 摘要\n\n(.*?)(?=\n---\n|$)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content[:300]

def scan_kb():
    """扫描知识库目录结构"""
    tree = []
    if not KB_ROOT.exists():
        return tree
    
    for cat_dir in sorted(KB_ROOT.iterdir()):
        if cat_dir.name.startswith("."):
            continue
        if cat_dir.is_file():
            continue
        
        category = cat_dir.name
        children = []
        
        for sub_dir in sorted(cat_dir.iterdir()):
            if sub_dir.name.startswith("."):
                continue
            if sub_dir.is_file():
                continue
            
            articles = []
            for file in sorted(sub_dir.rglob("*.md")):
                rel_path = str(file.relative_to(KB_ROOT))
                text = file.read_text(encoding="utf-8", errors="ignore")
                fm, body = parse_frontmatter(text)
                articles.append({
                    "path": rel_path,
                    "title": fm.get("title", file.stem),
                    "date": fm.get("date", ""),
                    "source": fm.get("source", ""),
                    "category": fm.get("category", category),
                    "summary_method": fm.get("summary_method", ""),
                    "summary": extract_summary(body),
                })
            
            if articles:
                children.append({
                    "name": sub_dir.name,
                    "articles": articles
                })
        
        if children:
            tree.append({
                "category": category,
                "children": children
            })
    
    return tree

def get_article(rel_path):
    """获取单篇文章"""
    filepath = KB_ROOT / rel_path
    if not filepath.exists():
        return None
    
    text = filepath.read_text(encoding="utf-8", errors="ignore")
    fm, body = parse_frontmatter(text)
    
    # 分离摘要和原文
    summary = ""
    full_text = body
    match = re.search(r'## 📝 摘要\n\n(.*?)(?=\n---\n)', body, re.DOTALL)
    if match:
        summary = match.group(1).strip()
        full_text = body[match.end():].strip()
        full_text = re.sub(r'^---\n*', '', full_text).strip()
        full_text = re.sub(r'^## 📄 原文\n*', '', full_text).strip()
    
    return {
        "path": rel_path,
        "title": fm.get("title", ""),
        "date": fm.get("date", ""),
        "source": fm.get("source", ""),
        "category": fm.get("category", ""),
        "summary_method": fm.get("summary_method", ""),
        "summary": summary,
        "content": full_text,
    }

def search_content(query):
    """搜索文章内容"""
    results = []
    query_lower = query.lower()
    
    for file in KB_ROOT.rglob("*.md"):
        text = file.read_text(encoding="utf-8", errors="ignore")
        fm, body = parse_frontmatter(text)
        
        title = fm.get("title", file.stem)
        summary = extract_summary(body)
        
        # 在标题、摘要、正文中搜索
        score = 0
        if query_lower in title.lower():
            score += 10
        if query_lower in summary.lower():
            score += 5
        if query_lower in body.lower():
            score += 2
        
        if score > 0:
            # 提取匹配的上下文
            idx = body.lower().find(query_lower)
            snippet = ""
            if idx >= 0:
                start = max(0, idx - 60)
                end = min(len(body), idx + 60 + len(query))
                snippet = body[start:end].replace("\n", " ").strip()
                if start > 0:
                    snippet = "..." + snippet
                if end < len(body):
                    snippet += "..."
            
            rel_path = str(file.relative_to(KB_ROOT))
            results.append({
                "path": rel_path,
                "title": title,
                "date": fm.get("date", ""),
                "category": fm.get("category", ""),
                "summary": summary[:200],
                "snippet": snippet,
                "score": score,
            })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:30]

class KBHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)
        
        # CORS
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        
        if path == "/api/structure":
            tree = scan_kb()
            self.wfile.write(json.dumps(tree, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/search":
            query = params.get("q", [""])[0]
            results = search_content(query)
            self.wfile.write(json.dumps(results, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/article":
            article_path = params.get("path", [""])[0]
            article = get_article(article_path)
            self.wfile.write(json.dumps(article, ensure_ascii=False).encode("utf-8"))
        elif path == "/" or path == "":
            # 返回前端页面
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
            self.wfile.write(html.encode("utf-8"))
        elif path.endswith(".html") or path.endswith(".css") or path.endswith(".js"):
            # 静态文件
            filepath = WEB_ROOT / path.lstrip("/")
            if filepath.exists():
                content_type = {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "application/javascript",
                }.get(filepath.suffix, "text/plain")
                self.send_response(200)
                self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                self.end_headers()
                self.wfile.write(filepath.read_bytes())
            else:
                self.send_response(404)
                self.wfile.write(b"Not found")
        else:
            self.wfile.write(json.dumps({"error": "Not found"}, ensure_ascii=False).encode("utf-8"))
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 静默模式

if __name__ == "__main__":
    port = 8765
    print(f"📚 知识库服务已启动: http://localhost:{port}")
    server = http.server.HTTPServer(("127.0.0.1", port), KBHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
